"""SoAI - Speech transcription child task admission and settlement [backend/core/media/speech_child_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError, SoAIError, SoAITimeoutError
from core.events.completion_signals import EventDispatchCompletion
from core.events.completion_waiting import EventPublicationReceipt
from core.events.types_models_requests import (
    AudioTranscriptionRequestReceived,
    AudioTranslationRequestReceived,
)
from core.files.operations import async_remove_if_exists
from core.logging.trace import get_logger
from core.media.speech_setup import SpeechTask, speech_task_endpoint
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.request_sources import REQUEST_SOURCE_SYSTEM
from core.runtime.soai_identifiers import create_system_id
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.task_cancellation import cancel
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.users.user_id import coerce_user_id

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.events.types_base import Event
    from core.media.transcription_contracts import SpeechChunkRequest
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import (
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
        TaskTypeRoutingServiceProtocol,
    )
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "MEDIA_TRANSCRIPTION_TASK_METADATA_KEY",
    "SPEECH_CHILD_SETTLEMENT_SECONDS",
    "SpeechChildTask",
    "SpeechChildTaskOwner",
    "SpeechChildTaskOwnerDependencies",
    "is_media_transcription_child",
)

MEDIA_TRANSCRIPTION_TASK_METADATA_KEY = "media_transcription"
SPEECH_CHILD_SETTLEMENT_SECONDS = CONTROL_TIMEOUT_SEC
LOGGER_NAME = "SoAI.core.media.speech_child_tasks"
OPERATION_PUBLISH = "core.media.speech_child_tasks.publish"
OPERATION_SETTLE = "core.media.speech_child_tasks.settle"
_STAGED_FILE_PREFIX = "media-transcription-"
_RESPONSE_FORMAT = "verbose_json"


@dataclass(slots=True)
class SpeechChildTask:
    task_id: str
    context: RequestContext
    reply_queue: asyncio.Queue[Event]
    staged_path: str
    completion: EventDispatchCompletion = field(default_factory=EventDispatchCompletion)

    @property
    def published(self) -> bool:
        return self.completion.snapshot().was_enqueued


@dataclass(frozen=True, slots=True)
class SpeechChildTaskOwnerDependencies:
    event_bus: EventBusProtocol
    task_registry: TaskRegistryProtocol
    task_type_routing: TaskTypeRoutingServiceProtocol
    temp_root: str
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SpeechChildTaskOwnerDependencies",
            event_bus=self.event_bus,
            task_registry=self.task_registry,
            task_type_routing=self.task_type_routing,
            temp_root=self.temp_root,
            finalizer_tracker=self.finalizer_tracker,
        )


def is_media_transcription_child(task: Task) -> bool:
    return isinstance(task.metadata.get(MEDIA_TRANSCRIPTION_TASK_METADATA_KEY), dict)


def _stage_chunk(source_path: str, staged_path: str) -> None:
    os.chmod(source_path, 0o600)
    os.replace(source_path, staged_path)


def _timestamp_granularities(request: SpeechChunkRequest) -> list[str]:
    if request.options.include_word_timestamps:
        return ["segment", "word"]
    return ["segment"]


def _build_event(
    child: SpeechChildTask, request: SpeechChunkRequest
) -> AudioTranscriptionRequestReceived | AudioTranslationRequestReceived:
    filename = f"chunk-{request.chunk_index:06d}.wav"
    capabilities = (speech_task_endpoint(request.options.task),)
    if request.options.task is SpeechTask.TRANSLATE:
        return AudioTranslationRequestReceived(
            reply_channel=child.reply_queue,
            context=child.context,
            temp_file_path=child.staged_path,
            original_filename=filename,
            audio_input_bytes=request.byte_count,
            model=request.model.universal_id,
            response_format=_RESPONSE_FORMAT,
            language=request.options.language,
            decoding_parameters=request.model.decoding_parameters,
            timestamp_granularities=_timestamp_granularities(request),
            required_capabilities=capabilities,
            required_modalities=("audio",),
        )
    return AudioTranscriptionRequestReceived(
        reply_channel=child.reply_queue,
        context=child.context,
        temp_file_path=child.staged_path,
        original_filename=filename,
        audio_input_bytes=request.byte_count,
        model=request.model.universal_id,
        language=request.options.language,
        decoding_parameters=request.model.decoding_parameters,
        response_format=_RESPONSE_FORMAT,
        timestamp_granularities=_timestamp_granularities(request),
        required_capabilities=capabilities,
        required_modalities=("audio",),
    )


class SpeechChildTaskOwner:
    def __init__(self, deps: SpeechChildTaskOwnerDependencies) -> None:
        self._event_bus = deps.event_bus
        self._task_registry = deps.task_registry
        self._task_type_routing = deps.task_type_routing
        self._temp_root = deps.temp_root
        self._finalizer_tracker = deps.finalizer_tracker
        self._settlements: set[asyncio.Task[None]] = set()

    async def create(self, request: SpeechChunkRequest) -> SpeechChildTask:
        creation = asyncio.create_task(
            self._create(request), name="media-transcription-create-child"
        )
        try:
            return await asyncio.shield(creation)
        except asyncio.CancelledError:
            finalizer = asyncio.create_task(
                self._settle_creation(creation), name="media-transcription-settle-created-child"
            )
            self._settlements.add(finalizer)
            finalizer.add_done_callback(self._settlements.discard)
            self._finalizer_tracker.track_finalizer(finalizer)
            raise

    async def await_settlements(self) -> None:
        if not self._settlements:
            return
        _, pending = await asyncio.wait(
            tuple(self._settlements), timeout=SPEECH_CHILD_SETTLEMENT_SECONDS
        )
        if pending:
            raise ServiceUnavailableError(
                "Media transcription task creation cleanup is still pending.",
                operation=OPERATION_SETTLE,
            )

    async def _settle_creation(self, creation: asyncio.Task[SpeechChildTask]) -> None:
        child = await creation
        await self.settle(child, "Media transcription ended before child admission.")

    async def _create(self, request: SpeechChunkRequest) -> SpeechChildTask:
        parent_context = request.request_context
        event_type = (
            AudioTranslationRequestReceived
            if request.options.task is SpeechTask.TRANSLATE
            else AudioTranscriptionRequestReceived
        )
        staged_path = os.path.abspath(
            os.path.join(self._temp_root, f"{_STAGED_FILE_PREFIX}{secrets.token_hex(16)}.wav"),
        )
        cancellation_id = create_system_id(
            subsystem="media_transcription",
            include_random_suffix=True,
        )
        metadata: JSONDict = {
            "temp_file_path": staged_path,
            MEDIA_TRANSCRIPTION_TASK_METADATA_KEY: {
                "parent_task_id": parent_context.task_id,
                "trace_id": parent_context.trace_id,
                "chunk_index": request.chunk_index,
                "model": request.model.universal_id,
            },
        }
        task, reply_queue = await create_streaming_task(
            self._task_registry,
            task_type=self._task_type_routing.get_task_type_for_command(event_type),
            user_id=coerce_user_id(parent_context.user_id),
            owner_id=parent_context.task_id or parent_context.trace_id,
            owner_type="system",
            cancellation_id=cancellation_id,
            initial_status=TaskStatus.QUEUED,
            metadata=metadata,
            request_source=REQUEST_SOURCE_SYSTEM,
            delivery_mode="streaming",
        )
        return SpeechChildTask(
            task_id=task.task_id,
            context=clone_request_context(
                parent_context,
                task_id=task.task_id,
                cancellation_id=cancellation_id,
            ),
            reply_queue=reply_queue,
            staged_path=staged_path,
        )

    async def stage_and_publish(self, child: SpeechChildTask, request: SpeechChunkRequest) -> None:
        await run_joined_thread_call(
            _stage_chunk,
            request.file_path,
            child.staged_path,
            task_name="media-transcription-stage-chunk",
        )
        event = _build_event(child, request)
        try:
            await self._event_bus.publish(event, child.completion)
            await EventPublicationReceipt(
                event_type=type(event).__name__,
                operation=OPERATION_PUBLISH,
                completion_signal=child.completion,
            ).wait_for_completion(request.deadline_monotonic)
        except (SoAIError, TimeoutError) as exception:
            if child.published:
                log_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message="Media transcription dispatch outcome is uncertain; awaiting the pool.",
                    operation=OPERATION_PUBLISH,
                    details={"task_id": child.task_id},
                    level="warning",
                )
                return
            raise ServiceUnavailableError(
                "Speech transcription could not be dispatched.",
                operation=OPERATION_PUBLISH,
                cause=exception,
            ) from exception

    async def settle(self, child: SpeechChildTask, reason: str) -> None:
        try:
            async with asyncio.timeout(SPEECH_CHILD_SETTLEMENT_SECONDS):
                await self._settle(child, reason)
        except (TimeoutError, SoAITimeoutError):
            get_logger(LOGGER_NAME).warning(
                "Media transcription task [%s] did not settle within %.0f seconds; its input stays owned by the task until it terminates or restart recovery runs.",
                child.task_id,
                SPEECH_CHILD_SETTLEMENT_SECONDS,
            )

    async def _settle(self, child: SpeechChildTask, reason: str) -> None:
        if not child.published:
            await finalize(
                self._task_registry,
                child.task_id,
                TaskStatus.CANCELLED,
                error_message=reason,
                status_message=reason,
            )
            await async_remove_if_exists(child.staged_path)
            return
        task = await self._task_registry.get(child.task_id, force_refresh=True)
        if task is None or task.status.is_terminal():
            return
        await cancel(self._task_registry, child.task_id, reason, context=child.context)
        await self._task_registry.wait_for_completion(
            child.task_id,
            timeout=SPEECH_CHILD_SETTLEMENT_SECONDS,
        )

"""SoAI - Plugin-pool speech-to-text chunk gateway [backend/core/media/speech_transcription_gateway.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import cancel_and_await
from core.di.validation import require_dependencies
from core.errors.exceptions import (
    ApiError,
    ModelOutputContractError,
    ServiceUnavailableError,
    StateError,
)
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.events.inference_terminal_handlers import build_inference_terminal_handlers
from core.events.non_streaming_hard_deadline import run_hard_deadline_event_loop
from core.events.types_models_streaming import InferenceResultEvent
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent
from core.media.speech_child_tasks import (
    SPEECH_CHILD_SETTLEMENT_SECONDS,
    SpeechChildTask,
    SpeechChildTaskOwner,
)
from core.media.speech_errors import build_transcription_option_error
from core.media.speech_selection import (
    SpeechSelectorType,
    parse_speech_model_selector,
    select_speech_model,
)
from core.media.transcript_normalization import normalize_verbose_transcript
from core.models.reference_resolution import resolve_model_reference
from core.openai.audio_upload_responses import (
    is_audio_upload_error_response,
    read_audio_upload_error_response,
)
from core.runtime.shutdown_errors import (
    SERVER_SHUTTING_DOWN_MESSAGE,
    ServerShuttingDownError,
)
from core.tasks.enums import TaskStatus

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.media.protocols import SpeechCatalogProtocol
    from core.media.speech_selection import ResolvedSpeechModel
    from core.media.speech_setup import SpeechTask
    from core.media.transcription_contracts import SpeechChunkRequest
    from core.media.types import TranscriptionChunkResult
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )

__all__ = ("SpeechTranscriptionGateway", "SpeechTranscriptionGatewayDependencies")

OPERATION = "core.media.speech_transcription_gateway"
_CANCELLED_REASON = "Media transcription was cancelled."
_TIMEOUT_MESSAGE = "Speech-to-text did not finish before the extraction deadline."
_FAILED_MESSAGE = "Speech-to-text failed"


@dataclass(frozen=True, slots=True)
class SpeechTranscriptionGatewayDependencies:
    children: SpeechChildTaskOwner
    speech_catalog: SpeechCatalogProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    virtual_model_service: VirtualModelServiceProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SpeechTranscriptionGatewayDependencies",
            children=self.children,
            speech_catalog=self.speech_catalog,
            model_resolution_service=self.model_resolution_service,
            model_information_service=self.model_information_service,
            virtual_model_service=self.virtual_model_service,
        )


def _failure(message: str | None) -> ServiceUnavailableError:
    detail = (message or "").strip()
    return ServiceUnavailableError(
        f"{_FAILED_MESSAGE}: {detail}" if detail else f"{_FAILED_MESSAGE}.",
        operation=OPERATION,
    )


class SpeechTranscriptionGateway:
    def __init__(self, deps: SpeechTranscriptionGatewayDependencies) -> None:
        self._speech_catalog = deps.speech_catalog
        self._model_resolution_service = deps.model_resolution_service
        self._model_information_service = deps.model_information_service
        self._virtual_model_service = deps.virtual_model_service
        self._children = deps.children
        self._active: set[asyncio.Task[TranscriptionChunkResult]] = set()
        self._closed = False

    async def resolve_model(self, *, selector: str, task: SpeechTask) -> ResolvedSpeechModel:
        self._require_open()
        parsed = parse_speech_model_selector(selector)
        snapshot = await self._speech_catalog.snapshot_speech_catalog()
        if parsed.type is not SpeechSelectorType.REFERENCE:
            return select_speech_model(snapshot, selector=parsed, task=task)
        reference = await resolve_model_reference(
            model_name=parsed.value,
            model_resolution_service=self._model_resolution_service,
            virtual_model_get=self._virtual_model_service.virtual_model_get,
        )
        concrete = reference is not None and not reference.is_virtual
        reference_record = (
            await self._model_information_service.model_get_info(reference.universal_ids[0])
            if concrete and reference is not None and len(reference.universal_ids) == 1
            else None
        )
        return select_speech_model(
            snapshot,
            selector=parsed,
            task=task,
            reference=reference,
            reference_record=reference_record,
        )

    async def transcribe_chunk(self, request: SpeechChunkRequest) -> TranscriptionChunkResult:
        self._require_open()
        operation = asyncio.create_task(self._run_chunk(request), name="media-transcription-chunk")
        self._active.add(operation)
        operation.add_done_callback(self._chunk_finished)
        return await operation

    def _chunk_finished(self, operation: asyncio.Task[TranscriptionChunkResult]) -> None:
        self._active.discard(operation)
        if not operation.cancelled():
            operation.exception()

    async def _run_chunk(self, request: SpeechChunkRequest) -> TranscriptionChunkResult:
        self._require_open()
        child: SpeechChildTask | None = None
        settled = False
        try:
            async with asyncio.timeout_at(request.deadline_monotonic):
                await self.resolve_model(
                    selector=request.model.universal_id, task=request.options.task
                )
                child = await self._children.create(request)
                self._require_open()
                await self._children.stage_and_publish(child, request)
                result = await self._await_child(child, request)
            settled = True
            return result
        finally:
            if child is not None and not settled:
                await uncancel_then_cleanup(self._children.settle(child, _CANCELLED_REASON))

    async def shutdown(self) -> None:
        self._closed = True
        pending = await cancel_and_await(
            tuple(self._active),
            task_label="media transcription operations",
            timeout_sec=SPEECH_CHILD_SETTLEMENT_SECONDS,
        )
        if pending:
            raise ServiceUnavailableError(
                "Media transcription cleanup is still pending.", operation=OPERATION
            )
        await self._children.await_settlements()

    def _require_open(self) -> None:
        if self._closed:
            raise ServerShuttingDownError(SERVER_SHUTTING_DOWN_MESSAGE, operation=OPERATION)

    async def _await_child(
        self,
        child: SpeechChildTask,
        request: SpeechChunkRequest,
    ) -> TranscriptionChunkResult:
        async def next_event(timeout_seconds: float) -> Event:
            return await asyncio.wait_for(child.reply_queue.get(), timeout=timeout_seconds)

        async def handle_result(event: Event) -> TranscriptionChunkResult:
            if not isinstance(event, InferenceResultEvent):
                raise StateError("Expected InferenceResultEvent.")
            return self._read_result(request, event)

        async def handle_error(event: Event) -> TranscriptionChunkResult:
            if not isinstance(event, ErrorEvent):
                raise StateError("Expected ErrorEvent.")
            error = _failure(event.public_error.message if event.public_error else event.message)
            if event.public_error is not None:
                apply_public_error_payload(error, event.public_error)
            raise error

        async def handle_complete(event: Event) -> TranscriptionChunkResult:
            if not isinstance(event, TaskCompleteEvent):
                raise StateError("Expected TaskCompleteEvent.")
            if event.status == TaskStatus.CANCELLED.value:
                raise TaskCancelledError(
                    child.context.cancellation_id or child.task_id,
                    event.error_message or _CANCELLED_REASON,
                )
            raise _failure(event.error_message or event.message)

        return await run_hard_deadline_event_loop(
            deadline_monotonic=request.deadline_monotonic,
            next_event=next_event,
            terminal_handlers=build_inference_terminal_handlers(
                handle_inference_result=handle_result,
                handle_error=handle_error,
                handle_complete=handle_complete,
            ),
            timeout_message=_TIMEOUT_MESSAGE,
            timeout_operation=OPERATION,
        )

    def _read_result(
        self,
        request: SpeechChunkRequest,
        event: InferenceResultEvent,
    ) -> TranscriptionChunkResult:
        if not is_audio_upload_error_response(event.payload):
            return normalize_verbose_transcript(event.payload)
        status_code, error_payload = read_audio_upload_error_response(event.payload)
        message_value = error_payload.get("message")
        message = message_value if isinstance(message_value, str) else "Request rejected."
        param_value = error_payload.get("param")
        param = param_value if isinstance(param_value, str) else None
        if status_code in {400, 422} and param in {
            "response_format",
            "timestamp_granularities",
            "language",
            "temperature",
            "condition_on_previous_text",
        }:
            raise build_transcription_option_error(
                f"{request.model.label} rejected the transcription request: {message}",
                model=request.model.universal_id,
                param=param,
            )
        code = error_payload.get("code", error_payload["type"])
        if isinstance(code, bool) or not isinstance(code, str | int):
            raise ModelOutputContractError("Speech-to-text returned an invalid error code.")
        error = ApiError(message, code=code, http_status=status_code, operation=OPERATION)
        apply_public_error_payload(
            error,
            ErrorPublicPayload(code=code, message=message, param=param, http_status=status_code),
        )
        raise error

"""SoAI - WebSocket OpenAI transcription deadline and task settlement [backend/features/api/routes/system/events/websocket_openai_audio/transcription_settlement.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from core.concurrency.wait_race import WaitRaceOutcome, wait_for_queue_or_event
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.public_projection import project_public_error
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.non_streaming_hard_deadline import run_hard_deadline_event_loop
from core.events.publication_errors import HardDeadlineExceededError
from core.system_api.websocket_run_events import build_websocket_run_event
from core.tasks.enums import TaskStatus
from core.types.json import is_json_dict
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_openai_audio.payloads import (
    build_openai_audio_transcription_cancelled,
    build_openai_audio_transcription_completed,
    build_openai_audio_transcription_error,
)
from features.api.routes.system.events.websocket_openai_audio.runtime import (
    TRANSCRIPTION_CANCELLATION_UNCONFIRMED_CODE,
    TRANSCRIPTION_SETTLEMENT_SECONDS,
    build_transcription_deadline_error,
    request_transcription_deadline_cancellation,
)
from features.api.routes.system.events.websocket_openai_result_collection import (
    build_openai_ws_result_handlers,
)
from features.api.streaming.stream_cancel import safe_cancel_streaming_task

if TYPE_CHECKING:
    from core.events.non_streaming_hard_deadline import TerminalEventHandler
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue
    from features.api.streaming.websocket_openai_runtime import (
        OpenAiAudioTranscriptionCancellation,
        OpenAiAudioTranscriptionRuntime,
    )

__all__ = ("TranscriptionSettlement", "settle_openai_audio_transcription")

OPERATION_TRANSCRIPTION_COLLECT = "api_system.websocket.openai_audio.transcription.collect"
OPERATION_TRANSCRIPTION_SETTLE = "api_system.websocket.openai_audio.transcription.settle"
TRANSCRIPTION_RESULT_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)
TRANSCRIPTION_FAILURE_REASON = "Audio transcription result collection failed."


@dataclass(frozen=True, slots=True)
class TranscriptionSettlement:
    event: JSONDict
    relinquished: bool


@dataclass(frozen=True, slots=True)
class _TranscriptionCollection:
    payload: JSONValue | None
    error: SoAIError | None

    @property
    def settled(self) -> bool:
        return self.payload is not None or self.error is not None


def _build_transcription_finalization_result(payload: JSONValue) -> JSONDict:
    if is_json_dict(payload):
        return payload
    return {"result": payload}


async def _collect_transcription(
    *,
    deadline_monotonic: float,
    next_event: Callable[[float], Awaitable[Event]],
    terminal_handlers: tuple[TerminalEventHandler[Event, JSONValue], ...],
    logger: LoggerProtocol,
    trace_id: str | None,
) -> _TranscriptionCollection:
    try:
        payload = await run_hard_deadline_event_loop(
            deadline_monotonic=deadline_monotonic,
            next_event=next_event,
            terminal_handlers=terminal_handlers,
            timeout_message="Audio transcription did not settle before its deadline.",
            timeout_operation=OPERATION_TRANSCRIPTION_COLLECT,
        )
    except HardDeadlineExceededError:
        return _TranscriptionCollection(payload=None, error=None)
    except TRANSCRIPTION_RESULT_EXCEPTIONS as exception:
        if not isinstance(exception, SoAIError):
            log_exception(
                logger,
                exception,
                message="OpenAI transcription result collection failed.",
                operation=OPERATION_TRANSCRIPTION_COLLECT,
                trace_id=trace_id,
                level="error",
            )
        return _TranscriptionCollection(
            payload=None,
            error=coerce_to_soai_error(exception, operation=OPERATION_TRANSCRIPTION_COLLECT),
        )
    return _TranscriptionCollection(payload=payload, error=None)


def _build_settlement_event(
    *,
    run_id: str,
    task_id: str,
    task: Task | None,
    collection: _TranscriptionCollection,
    cancellation: OpenAiAudioTranscriptionCancellation | None,
    trace_id: str | None,
) -> JSONDict:
    status = task.status if task is not None else None
    if status is TaskStatus.COMPLETED and collection.payload is not None:
        return build_openai_audio_transcription_completed(
            run_id=run_id,
            task_id=task_id,
            result=collection.payload,
        )
    if cancellation is not None and status is TaskStatus.CANCELLED:
        if cancellation.cause == "deadline":
            return build_transcription_deadline_error(run_id=run_id, task_id=task_id)
        return build_openai_audio_transcription_cancelled(
            run_id=run_id,
            reason=cancellation.reason,
            task_id=task_id,
        )
    if cancellation is not None and (status is None or not status.is_terminal()):
        return build_openai_audio_transcription_error(
            run_id=run_id,
            message=(
                "Audio transcription cancellation was not confirmed within "
                f"{TRANSCRIPTION_SETTLEMENT_SECONDS:.0f} seconds."
            ),
            code=TRANSCRIPTION_CANCELLATION_UNCONFIRMED_CODE,
            task_id=task_id,
        )
    if collection.error is None:
        return build_openai_audio_transcription_error(
            run_id=run_id,
            message="Audio transcription ended without a result.",
            code="server_error",
            task_id=task_id,
        )
    public_error = project_public_error(collection.error, trace_id=trace_id)
    return build_websocket_run_event(
        event_type=WebSocketEventTypes.OPENAI_AUDIO_TRANSCRIPTION_ERROR,
        run_id=run_id,
        task_id=task_id,
        fields={
            "code": public_error.code,
            "message": public_error.message,
            "error": public_error.to_dict(),
        },
    )


async def settle_openai_audio_transcription(
    *,
    run_id: str,
    task_id: str,
    runtime: OpenAiAudioTranscriptionRuntime,
    registry: TaskRegistryProtocol,
    reply_queue: asyncio.Queue[Event],
    context: RequestContext,
    logger: LoggerProtocol,
) -> TranscriptionSettlement:
    terminal_handlers = build_openai_ws_result_handlers(
        registry=registry,
        task_id=task_id,
        include_payload_event=True,
        finalization_result_builder=_build_transcription_finalization_result,
    )

    async def next_event_or_cancellation(_remaining: float) -> Event:
        race = await wait_for_queue_or_event(reply_queue, runtime.cancellation_requested)
        if race.outcome is WaitRaceOutcome.AWAITABLE_COMPLETED and race.value is not None:
            return race.value
        raise TimeoutError("Audio transcription cancellation was requested.")

    async def next_event(remaining: float) -> Event:
        return await asyncio.wait_for(reply_queue.get(), timeout=remaining)

    deadline_timer = asyncio.get_running_loop().call_later(
        runtime.deadline.remaining_seconds(),
        request_transcription_deadline_cancellation,
        runtime,
    )
    try:
        collection = await _collect_transcription(
            deadline_monotonic=runtime.deadline.deadline_monotonic,
            next_event=next_event_or_cancellation,
            terminal_handlers=terminal_handlers,
            logger=logger,
            trace_id=context.trace_id,
        )
    finally:
        deadline_timer.cancel()
    if not collection.settled and runtime.cancellation is None:
        request_transcription_deadline_cancellation(runtime)
    task = await registry.get(task_id, force_refresh=True)
    if task is not None and not task.status.is_terminal():
        await safe_cancel_streaming_task(
            registry,
            task_id,
            (
                runtime.cancellation.reason
                if runtime.cancellation is not None
                else TRANSCRIPTION_FAILURE_REASON
            ),
            context,
            logger,
            OPERATION_TRANSCRIPTION_SETTLE,
        )
        if collection.settled:
            task = await registry.wait_for_completion(
                task_id,
                timeout=TRANSCRIPTION_SETTLEMENT_SECONDS,
            )
    if not collection.settled:
        collection = await _collect_transcription(
            deadline_monotonic=deadline_after(TRANSCRIPTION_SETTLEMENT_SECONDS).deadline_monotonic,
            next_event=next_event,
            terminal_handlers=terminal_handlers,
            logger=logger,
            trace_id=context.trace_id,
        )
        task = await registry.get(task_id, force_refresh=True)
    relinquished = task is not None and task.status.is_terminal()
    if not relinquished:
        logger.warning(
            "Audio transcription task did not settle after cancellation (run_id=%s, task_id=%s, cause=%s, settlement_seconds=%.0f).",
            run_id,
            task_id,
            runtime.cancellation.cause if runtime.cancellation is not None else "failure",
            TRANSCRIPTION_SETTLEMENT_SECONDS,
        )
    return TranscriptionSettlement(
        event=_build_settlement_event(
            run_id=run_id,
            task_id=task_id,
            task=task,
            collection=collection,
            cancellation=runtime.cancellation,
            trace_id=context.trace_id,
        ),
        relinquished=relinquished,
    )

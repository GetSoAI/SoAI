"""SoAI - Canonical conversation stream cancellation [backend/features/chat/conversation_stream_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import Event, current_task
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.cancellation_scope import (
    publish_and_verify_cancellation_scope_noncritical,
)
from core.tasks.task_cancellation import cancel
from core.validation.strings import coerce_optional_trimmed_str
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "cancel_conversation_stream_runtime",
    "claim_conversation_stream_runtime_cancellation",
    "mark_conversation_stream_runtime_cancellation_requested",
)

LOGGER_NAME = "SoAI.features.chat.conversation_stream_cancellation"
OPERATION_CANCEL_TASK = "chat.conversation_stream.cancel.task"


def _runtime_is_agentic(runtime: AssistantTimelineRuntime) -> bool:
    return coerce_optional_trimmed_str(runtime.agent_turn_id) is not None


def _runtime_has_claimed_agent_turn(runtime: AssistantTimelineRuntime) -> bool:
    return (
        coerce_optional_trimmed_str(runtime.agent_turn_id) is not None
        and coerce_optional_trimmed_str(runtime.agent_turn_execution_token) is not None
    )


def _resolve_runtime_cancellation_id(runtime: AssistantTimelineRuntime) -> str | None:
    return coerce_optional_trimmed_str(runtime.task_cancellation_id)


def _resolve_claimed_turn_cancellation_id(
    runtime: AssistantTimelineRuntime,
) -> str | None:
    return coerce_optional_trimmed_str(runtime.agent_turn_cancellation_id)


def mark_conversation_stream_runtime_cancellation_requested(
    runtime: AssistantTimelineRuntime,
    reason: str,
) -> None:
    if not runtime.cancellation_requested:
        runtime.cancellation_requested = True
        runtime.cancellation_reason = reason
    if runtime.detach_event is None:
        runtime.detach_event = Event()
    runtime.detach_event.set()


async def claim_conversation_stream_runtime_cancellation(
    runtime: AssistantTimelineRuntime,
    reason: str,
) -> bool:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        if (
            runtime.terminal_outcome_claim == "cancelled"
            and not runtime.terminal_finalization_started
            and not runtime.terminal_event_emitted
        ):
            mark_conversation_stream_runtime_cancellation_requested(runtime, reason)
            return True
        if (
            runtime.terminal_outcome_claim is not None
            or runtime.terminal_finalization_started
            or runtime.terminal_event_emitted
        ):
            return False
        runtime.terminal_outcome_claim = "cancelled"
        mark_conversation_stream_runtime_cancellation_requested(runtime, reason)
        return True


def _cancel_runner_task_directly(
    runtime: AssistantTimelineRuntime,
    logger: LoggerProtocol,
    trace_id: str,
) -> bool:
    runner_task = runtime.runner_task
    if runner_task is not None and not runner_task.done() and runner_task is not current_task():
        runner_task.cancel()
        return True
    if runner_task is None:
        resolved_state = "runner_task_not_registered"
    elif runner_task.done():
        resolved_state = "runner_task_already_done"
    else:
        resolved_state = "runner_task_is_current_task"
    logger.debug(
        "Conversation stream cancellation deferred to runner checkpoints (%s, conv_id=%s, request_id=%s, trace_id=%s).",
        resolved_state,
        runtime.conv_id,
        runtime.request_id,
        trace_id,
    )
    return False


async def _publish_and_verify_scope_cancel_noncritical(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    runtime: AssistantTimelineRuntime,
    reason: str,
    cancellation_id: str,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    return await publish_and_verify_cancellation_scope_noncritical(
        event_bus=api_dependencies.event_bus,
        cancellation_coordinator=api_dependencies.cancellation_coordinator,
        cancellation_history=api_dependencies.cancellation_history,
        context=context,
        reason=reason,
        cancellation_id=cancellation_id,
        logger=logger,
        publish_message="Failed to publish conversation stream cancellation (non-critical).",
        verify_message="Failed to verify conversation stream cancellation (non-critical).",
        level="debug",
        details={
            "conv_id": runtime.conv_id,
            "request_id": runtime.request_id,
            "cancellation_id": cancellation_id,
        },
    )


async def cancel_conversation_stream_runtime(
    *,
    api_dependencies: ApiDependencies,
    context: RequestContext,
    runtime: AssistantTimelineRuntime,
    reason: str,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    if runtime.terminal_finalization_started:
        return True
    cancellation_confirmed = _cancel_runner_task_directly(runtime, logger, context.trace_id)
    if _runtime_has_claimed_agent_turn(runtime):
        cancellation_id = _resolve_claimed_turn_cancellation_id(runtime)
        if cancellation_id:
            cancellation_confirmed = await _publish_and_verify_scope_cancel_noncritical(
                api_dependencies=api_dependencies,
                context=context,
                runtime=runtime,
                reason=reason,
                cancellation_id=cancellation_id,
            )
    elif _runtime_is_agentic(runtime) or not runtime.active_task_id:
        cancellation_id = _resolve_runtime_cancellation_id(runtime)
        if cancellation_id:
            cancellation_confirmed = await _publish_and_verify_scope_cancel_noncritical(
                api_dependencies=api_dependencies,
                context=context,
                runtime=runtime,
                reason=reason,
                cancellation_id=cancellation_id,
            )
    else:
        task_id = runtime.active_task_id
        try:
            cancelled_task = await cancel(
                api_dependencies.task_registry,
                task_id,
                reason=reason,
                context=context,
            )
            cancellation_confirmed = cancelled_task is not None
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to cancel conversation stream task (non-critical).",
                trace_id=context.trace_id,
                operation=OPERATION_CANCEL_TASK,
                level="debug",
                details={
                    "conv_id": runtime.conv_id,
                    "request_id": runtime.request_id,
                    "task_id": task_id,
                },
            )
            cancellation_confirmed = False
    return cancellation_confirmed

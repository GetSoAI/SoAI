"""SoAI - WebSocket chat stream admitted-task abort cancellation [backend/features/api/routes/system/events/websocket_chat_stream/admitted_abort_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.cancellation_scope import (
    publish_and_verify_cancellation_scope_noncritical,
)
from core.tasks.task_cancellation import cancel

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.runtime.streaming_inference_admission import (
        AgentStreamingTaskBundle,
    )
    from features.api.runtime.context import ApiContext

__all__ = ("cancel_admitted_ws_chat_stream_task_for_abort",)

OPERATION_POST_ADMISSION_ABORT_CANCEL_TASK = (
    "webui_ws_chat_stream.run.cancel_admitted_task_on_abort"
)


async def _publish_admitted_task_scope_cancel(
    *,
    api_context: ApiContext,
    context: RequestContext,
    bundle: AgentStreamingTaskBundle,
    reason: str,
    logger: LoggerProtocol,
) -> None:
    details: JSONDict = {
        "task_id": bundle.task.task_id,
        "cancellation_id": bundle.task.cancellation_id,
    }
    if await publish_and_verify_cancellation_scope_noncritical(
        event_bus=api_context.dependencies.event_bus,
        cancellation_coordinator=api_context.dependencies.cancellation_coordinator,
        cancellation_history=api_context.dependencies.cancellation_history,
        context=context,
        reason=reason,
        cancellation_id=bundle.task.cancellation_id,
        logger=logger,
        publish_message="Failed to publish cancellation scope for admitted chat stream task after direct cancel failed.",
        verify_message="Failed to verify cancellation scope for admitted chat stream task.",
        level="warning",
        details=details,
    ):
        return
    logger.warning(
        "Admitted chat stream task cancellation scope was not cancelled after fallback publish (task_id=%s, cancellation_id=%s, trace_id=%s).",
        bundle.task.task_id,
        bundle.task.cancellation_id,
        context.trace_id,
    )


async def cancel_admitted_ws_chat_stream_task_for_abort(
    *,
    api_context: ApiContext,
    context: RequestContext,
    bundle: AgentStreamingTaskBundle,
    reason: str,
    logger: LoggerProtocol,
) -> None:
    try:
        await cancel(
            api_context.dependencies.task_registry,
            bundle.task.task_id,
            reason=reason,
            context=context,
        )
        if await api_context.dependencies.cancellation_history.is_cancelled(
            bundle.task.cancellation_id,
        ):
            return
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to cancel admitted chat stream task during cancellation abort (non-critical).",
            trace_id=context.trace_id,
            operation=OPERATION_POST_ADMISSION_ABORT_CANCEL_TASK,
            level="debug",
            details={"task_id": bundle.task.task_id},
        )
    await _publish_admitted_task_scope_cancel(
        api_context=api_context,
        context=context,
        bundle=bundle,
        reason=reason,
        logger=logger,
    )

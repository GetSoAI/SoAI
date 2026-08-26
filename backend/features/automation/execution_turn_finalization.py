"""SoAI - Automation turn interruption finalization [backend/features/automation/execution_turn_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.task_cancellation import cancel
from features.assistant_timeline.assistant_timeline_terminal import (
    finalize_assistant_timeline_cancelled,
)

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )
    from features.assistant_timeline.models import AssistantTimelineRuntime
    from features.automation.execution_messages import AutomationConversationSession

__all__ = (
    "cancel_automation_turn_streaming_task_noncritical",
    "finalize_automation_turn_cancelled",
)

LOGGER_NAME = "SoAI.features.automation.execution_turn_finalization"
OPERATION_CANCEL_AFTER_INTERRUPTION = (
    "automation.execution_turn_finalization.cancel_after_interruption"
)


async def cancel_automation_turn_streaming_task_noncritical(
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    turn_context: RequestContext,
    session: AutomationConversationSession,
    exception: BaseException,
) -> None:
    if runtime.active_task_id is None:
        return
    try:
        await cancel(
            api_dependencies.task_registry,
            runtime.active_task_id,
            reason=str(exception),
            context=turn_context,
        )
    except RECOVERABLE_EXCEPTIONS as cancel_exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            cancel_exception,
            message=(
                "Failed to cancel automation streaming task after turn interruption "
                "(non-critical)."
            ),
            trace_id=turn_context.trace_id,
            operation=OPERATION_CANCEL_AFTER_INTERRUPTION,
            level="debug",
            details={"conv_id": session.conv_id, "request_id": runtime.request_id},
        )


async def finalize_automation_turn_cancelled(
    api_dependencies: ApiDependencies,
    *,
    runtime: AssistantTimelineRuntime,
    session_runtime: AssistantTimelineSession,
    turn_context: RequestContext,
    session: AutomationConversationSession,
    exception: BaseException,
    message: str,
) -> None:
    await cancel_automation_turn_streaming_task_noncritical(
        api_dependencies,
        runtime,
        turn_context,
        session,
        exception,
    )
    if not runtime.terminal_event_emitted and not runtime.terminal_finalization_started:
        await finalize_assistant_timeline_cancelled(session_runtime, message)

"""SoAI - WebSocket chat stream failure cleanup [backend/features/api/routes/system/events/websocket_chat_stream/failure_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.request_context import RequestContext
from features.api.runtime.chat_execution.runtime_quota import (
    release_ws_chat_stream_runtime_quota_noncritical,
)
from features.assistant_timeline.assistant_timeline_shutdown import (
    stop_timeline_session_tickers,
)
from features.chat.conversation_stream_cancellation import (
    cancel_conversation_stream_runtime,
)

if TYPE_CHECKING:
    from core.auth.protocols_database_api_keys import DatabaseAPIKeysProtocol
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.context import ApiContext
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = ("cleanup_ws_chat_stream_failure_noncritical",)

OPERATION_WEBUI_WS_CHAT_STREAM_RUN_CANCEL_TASK_AFTER_ERROR = (
    "webui_ws_chat_stream.run.cancel_task_after_error"
)


async def cleanup_ws_chat_stream_failure_noncritical(
    exception: Exception,
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    context: RequestContext,
    session: AssistantTimelineSession,
    database_api_keys: DatabaseAPIKeysProtocol,
) -> tuple[str, str]:
    runtime = session.runtime
    coerced = coerce_to_soai_error(exception, operation="webui_ws_chat_stream.run")
    await uncancel_then_cleanup(stop_timeline_session_tickers(session))
    if runtime.active_task_id or (
        runtime.agent_turn_id is not None and runtime.agent_turn_id.strip()
    ):
        try:
            await cancel_conversation_stream_runtime(
                api_dependencies=api_context.dependencies,
                context=context,
                runtime=runtime,
                reason=str(coerced),
            )
        except RECOVERABLE_EXCEPTIONS as cancel_exception:
            cancel_error = coerce_to_soai_error(
                cancel_exception,
                operation="webui_ws_chat_stream.run.cancel_task_after_error",
            )
            log_handled_exception(
                logger,
                cancel_error,
                message="Failed to cancel WebUI WebSocket chat stream task after stream error (non-critical).",
                trace_id=context.trace_id,
                operation=OPERATION_WEBUI_WS_CHAT_STREAM_RUN_CANCEL_TASK_AFTER_ERROR,
                level="debug",
                details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
            )
    await uncancel_then_cleanup(
        release_ws_chat_stream_runtime_quota_noncritical(
            database_api_keys=database_api_keys,
            runtime=runtime,
            logger=logger,
            trace_id=context.trace_id,
            operation="webui_ws_chat_stream.run.release_quota_after_error",
            message="Failed to release WebUI WebSocket chat stream quota after error.",
        ),
    )
    return str(coerced), str(coerced.code)

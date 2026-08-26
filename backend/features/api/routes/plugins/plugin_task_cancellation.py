"""SoAI - Plugin task cancellation helpers [backend/features/api/routes/plugins/plugin_task_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task_cancellation import cancel

__all__ = ("cancel_task_after_request_cancellation",)

OPERATION_FEATURES_API_ROUTES_PLUGINS_PLUGIN_TASK_CANCELLATION_CANCEL_TASK_AFTER_REQUEST_CANCELLATION = (
    "features.api.routes.plugins.plugin_task_cancellation.cancel_task_after_request_cancellation"
)


LOGGER_NAME = "SoAI.features.api.plugin_task_cancellation"


async def cancel_task_after_request_cancellation(
    *,
    registry: TaskRegistryProtocol,
    task_id: str,
    context: RequestContext,
    operation: str,
    trace_id: str | None,
) -> None:
    try:
        await cancel(
            registry,
            task_id,
            reason="Client disconnected.",
            context=context,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to cancel task after plugin request cancellation (non-critical).",
            operation=OPERATION_FEATURES_API_ROUTES_PLUGINS_PLUGIN_TASK_CANCELLATION_CANCEL_TASK_AFTER_REQUEST_CANCELLATION,
            trace_id=trace_id,
            details={"task_id": task_id, "operation": operation},
            level="debug",
        )

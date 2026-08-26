"""SoAI - Plugin cancellation notification helper [backend/orchestrator/execution/plugin_cancellation_notification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.request_context_cloning import clone_request_context
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from orchestrator.execution.event_context import resolve_event_context

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.tasks.orchestration_context import OrchestrationContext
    from core.tasks.task import Task

__all__ = ("notify_plugin_task_cancelled",)

OPERATION = "orchestrator.execution.plugin_cancellation_notification"


async def notify_plugin_task_cancelled(
    *,
    task: Task,
    plugin_instance: PluginInstanceProtocol,
    plugin_name: str,
    context_source: OrchestrationContext,
    logger: LoggerProtocol,
) -> None:
    try:
        cancel_context = clone_request_context(
            resolve_event_context(context_source, "cancel_task"),
            task_id=task.task_id,
            cancellation_id=task.cancellation_id,
        )
        await asyncio.wait_for(
            plugin_instance.cancel_task(task.task_id, cancel_context),
            timeout=INTERACTIVE_TIMEOUT_SEC,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION,
        )
        log_exception(
            logger,
            coerced,
            message=f"Failed to notify plugin '{plugin_name}' of cancellation for task [{task.task_id}]",
            operation=OPERATION,
            level="warning",
        )

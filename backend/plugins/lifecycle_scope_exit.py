"""SoAI - Plugin lifecycle scope exit handling [backend/plugins/lifecycle_scope_exit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from plugins.lifecycle_dependencies import PluginLifecycleDependencies

__all__ = ("finalize_scope_exit_if_needed",)

LOGGER_NAME = "SoAI.plugins.lifecycle_scope_exit"
OPERATION = "plugin_lifecycle.lifecycle_scope.exit_without_finalization"


async def finalize_scope_exit_if_needed(
    deps: PluginLifecycleDependencies,
    *,
    unified_task_id: str | None,
    task_type: str,
    plugin_name: str | None,
    mutation_fencing_token: int | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not unified_task_id:
        return
    registry = deps.task_registry
    try:
        record = await registry.get(unified_task_id, force_refresh=True)
        if record is None or record.status.is_terminal():
            return
        logger.error(
            "Lifecycle scope exited without task finalization (task_id=%s, task_type=%s, plugin=%s).",
            unified_task_id,
            task_type,
            plugin_name or "system",
        )
        await deps.task_finalize(
            registry,
            unified_task_id,
            TaskStatus.FAILED,
            error_code=500,
            error_message=(
                "Internal error: task handler exited without finalizing the task. Please check backend logs."
            ),
            mutation_fencing_token=mutation_fencing_token,
        )
    except RECOVERABLE_EXCEPTIONS as finalize_exception:
        log_exception(
            logger,
            finalize_exception,
            message="Failed to finalize unified task after lifecycle scope exit.",
            operation=OPERATION,
            details={"task_id": unified_task_id},
            level="warning",
        )

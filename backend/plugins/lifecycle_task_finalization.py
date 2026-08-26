"""SoAI - Plugin lifecycle task finalization on errors [backend/plugins/lifecycle_task_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from plugins.lifecycle_dependencies import PluginLifecycleDependencies

__all__ = ("finalize_task_on_error",)

LOGGER_NAME = "SoAI.plugins.lifecycle_task_finalization"
OPERATION = "plugin_lifecycle.finalize_task_on_error"


async def finalize_task_on_error(
    deps: PluginLifecycleDependencies,
    registry: TaskRegistryProtocol,
    *,
    task_id: str | None,
    exception: BaseException,
    mutation_fencing_token: int | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not task_id:
        return
    try:
        record = await registry.get(task_id)
        if record is None or record.status.is_terminal():
            return
        if isinstance(exception, asyncio.CancelledError):
            await deps.task_cancel(
                registry,
                task_id,
                reason="Operation cancelled",
                mutation_fencing_token=mutation_fencing_token,
            )
        else:
            await deps.task_finalize(
                registry,
                task_id,
                TaskStatus.FAILED,
                error_code=500,
                error_message=str(exception),
                mutation_fencing_token=mutation_fencing_token,
            )
    except RECOVERABLE_EXCEPTIONS as finalize_exception:
        log_exception(
            logger,
            finalize_exception,
            message="Failed to finalize unified task after lifecycle error.",
            operation=OPERATION,
            details={"task_id": task_id},
            level="warning",
        )

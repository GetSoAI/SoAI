"""SoAI - Automation run owner task progress updates [backend/features/automation/execution_owner_task_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_run_task_lifecycle import (
    normalize_automation_run_owner_task_id,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.tasks.enums import TaskStatus
from core.tasks.status_transitions import update_status

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.container.types import ApiDependencies

__all__ = ("update_run_owner_task_progress_noncritical",)


async def update_run_owner_task_progress_noncritical(
    api_dependencies: ApiDependencies,
    logger: LoggerProtocol,
    *,
    owner_task_id: str | None,
    progress_current: int,
    progress_total: int,
    status_message: str,
    operation: str,
    run_id: str,
    automation_id: str,
) -> None:
    normalized_owner_task_id = normalize_automation_run_owner_task_id(owner_task_id)
    if normalized_owner_task_id is None:
        return
    normalized_message = str(status_message or "").strip()
    if not normalized_message:
        return
    try:
        await update_status(
            api_dependencies.task_registry,
            normalized_owner_task_id,
            TaskStatus.WORKING,
            status_message=normalized_message,
            progress_current=max(0, int(progress_current)),
            progress_total=max(1, int(progress_total)),
        )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to update automation run owner task progress (non-critical).",
            operation=operation,
            level="debug",
            details={"run_id": run_id, "automation_id": automation_id},
        )

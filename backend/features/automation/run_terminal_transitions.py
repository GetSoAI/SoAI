"""SoAI - Automation run terminal transition helpers [backend/features/automation/run_terminal_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_run_task_lifecycle import (
    finalize_automation_run_owner_task,
)
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict
    from features.automation.internal_protocols import (
        AutomationRunTerminalDependenciesProtocol,
    )

    type AutomationRunTerminalStatus = Literal["completed", "cancelled", "abandoned", "error"]

__all__ = (
    "complete_automation_run_terminal",
    "finalize_automation_run_task_terminal",
    "resolve_failure_terminal_status",
)


def resolve_failure_terminal_status(
    *,
    is_timeout: bool,
    is_cancelled: bool,
) -> AutomationRunTerminalStatus:
    if is_timeout:
        return "error"
    if is_cancelled:
        return "cancelled"
    return "error"


async def complete_automation_run_terminal(
    api_dependencies: AutomationRunTerminalDependenciesProtocol,
    *,
    run_id: str,
    user_id: int,
    final_status: AutomationRunTerminalStatus,
    status_message: str | None = None,
    result_excerpt: str | None = None,
    finished_at_ms: int | None = None,
) -> JSONDict | None:
    resolved_finished_at_ms = epoch_ms() if finished_at_ms is None else finished_at_ms
    if final_status == "completed":
        return await api_dependencies.database_automation_runs.complete_run_completed(
            run_id,
            user_id,
            finished_at_ms=resolved_finished_at_ms,
            result_excerpt=result_excerpt,
        )
    normalized_message = str(status_message or "").strip()
    if not normalized_message:
        raise StateError("Automation terminal transition requires a status_message.")
    if final_status == "cancelled":
        return await api_dependencies.database_automation_runs.complete_run_cancelled(
            run_id,
            user_id,
            finished_at_ms=resolved_finished_at_ms,
            status_message=normalized_message,
            result_excerpt=result_excerpt,
        )
    if final_status == "abandoned":
        return await api_dependencies.database_automation_runs.complete_run_abandoned(
            run_id,
            user_id,
            finished_at_ms=resolved_finished_at_ms,
            status_message=normalized_message,
            result_excerpt=result_excerpt,
        )
    if final_status == "error":
        return await api_dependencies.database_automation_runs.complete_run_error(
            run_id,
            user_id,
            finished_at_ms=resolved_finished_at_ms,
            status_message=normalized_message,
            result_excerpt=result_excerpt,
        )
    raise StateError("Automation run terminal status is invalid.")


async def finalize_automation_run_task_terminal(
    api_dependencies: AutomationRunTerminalDependenciesProtocol,
    *,
    owner_task_id: str | None,
    final_status: AutomationRunTerminalStatus,
    error_message: str | None = None,
    error_code: int | None = None,
) -> None:
    await finalize_automation_run_owner_task(
        api_dependencies.task_registry,
        owner_task_id=owner_task_id,
        final_status=final_status,
        error_code=error_code,
        error_message=error_message,
    )

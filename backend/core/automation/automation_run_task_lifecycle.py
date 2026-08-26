"""SoAI - Automation run owned-task lifecycle [backend/core/automation/automation_run_task_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.automation.automation_identifiers import build_automation_run_cancellation_id
from core.errors.exceptions import StateError
from core.execution.owned_execution_tasks import (
    create_owned_execution_task,
    finalize_owned_execution_task,
    mark_owned_execution_running,
)
from core.tasks.errors import TaskIDCollisionError
from core.validation.record_fields import (
    require_int,
    require_non_empty_str,
    require_str_list,
)

if TYPE_CHECKING:
    from typing import Literal

    from core.automation.protocols_database import DatabaseAutomationRunsProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict, JSONValue

    type AutomationRunTaskTerminalStatus = Literal["completed", "cancelled", "abandoned", "error"]

__all__ = (
    "ensure_automation_run_owner_task",
    "ensure_automation_run_owner_task_attached",
    "finalize_abandoned_automation_owner_task_ids",
    "finalize_automation_run_owner_task",
    "finalize_created_automation_run_task_for_terminal_run",
    "mark_automation_run_task_working",
    "normalize_automation_run_owner_task_id",
    "read_automation_run_owner_task_id",
    "require_automation_identifier_list",
)


def read_automation_run_owner_task_id(run_record: JSONDict) -> str | None:
    owner_task_id_value = run_record.get("owner_task_id")
    return normalize_automation_run_owner_task_id(owner_task_id_value)


def normalize_automation_run_owner_task_id(owner_task_id_value: JSONValue | None) -> str | None:
    if not isinstance(owner_task_id_value, str):
        return None
    normalized_owner_task_id = owner_task_id_value.strip()
    return normalized_owner_task_id or None


def require_automation_identifier_list(
    identifier_list_value: JSONValue,
    *,
    label: str,
) -> tuple[str, ...]:
    return tuple(
        require_str_list(
            identifier_list_value,
            label=f"Automation {label}",
            build_error=StateError,
            allow_empty=True,
        ),
    )


def _resolve_initial_task_status(status: str) -> str | None:
    if status in {"queued", "running"}:
        return status
    return None


def _requires_owner_task_id(status: str) -> bool:
    return status in {"queued", "running"}


def _resolve_terminal_status(status: str) -> AutomationRunTaskTerminalStatus:
    if status == "completed":
        return "completed"
    if status == "cancelled":
        return "cancelled"
    if status == "abandoned":
        return "abandoned"
    return "error"


def _resolve_terminal_status_message(status: AutomationRunTaskTerminalStatus) -> str:
    if status == "completed":
        return "Automation run completed."
    if status == "cancelled":
        return "Automation run cancelled."
    if status == "abandoned":
        return "Automation run abandoned."
    if status == "error":
        return "Automation run failed."
    raise StateError("Automation run task final status is invalid.")


async def ensure_automation_run_owner_task(
    database_automation_runs: DatabaseAutomationRunsProtocol,
    task_registry: TaskRegistryProtocol,
    *,
    run_record: JSONDict,
) -> str | None:
    existing_owner_task_id = read_automation_run_owner_task_id(run_record)
    if existing_owner_task_id is not None:
        return existing_owner_task_id
    initial_status = _resolve_initial_task_status(
        require_non_empty_str(
            run_record.get("status"),
            label="Automation status",
            build_error=StateError,
        ),
    )
    if initial_status is None:
        return None
    run_id = require_non_empty_str(
        run_record.get("run_id"),
        label="Automation run_id",
        build_error=StateError,
    )
    user_id = require_int(
        run_record.get("user_id"),
        label="Automation user_id",
        build_error=StateError,
        minimum=1,
    )
    automation_id_value = run_record.get("automation_id")
    automation_id = automation_id_value.strip() if isinstance(automation_id_value, str) else ""
    created_task = False
    try:
        await create_owned_execution_task(
            task_registry,
            user_id=user_id,
            owner_id=f"automation_run:{run_id}",
            owner_type="system",
            owner_task_id=run_id,
            cancellation_id=build_automation_run_cancellation_id(run_id),
            initial_status=initial_status,
            status_message=("Queued" if initial_status == "queued" else "Running"),
            metadata={"run_id": run_id, "automation_id": automation_id},
        )
        created_task = True
    except TaskIDCollisionError:
        created_task = False
    attached_run_record = await database_automation_runs.attach_owner_task_id(
        run_id,
        user_id,
        run_id,
    )
    if isinstance(attached_run_record, dict):
        return run_id
    refreshed_run_record = await database_automation_runs.get_run(run_id, user_id)
    if isinstance(refreshed_run_record, dict):
        refreshed_owner_task_id = read_automation_run_owner_task_id(refreshed_run_record)
        if refreshed_owner_task_id is not None:
            return refreshed_owner_task_id
    if created_task:
        status_message_value = (
            refreshed_run_record.get("status_message")
            if isinstance(refreshed_run_record, dict)
            else None
        )
        error_message = (
            status_message_value.strip()
            if isinstance(status_message_value, str) and status_message_value.strip()
            else "Automation run ownership attachment failed."
        )
        refreshed_status = (
            require_non_empty_str(
                refreshed_run_record.get("status"),
                label="Automation status",
                build_error=StateError,
            )
            if isinstance(refreshed_run_record, dict)
            else ""
        )
        await finalize_created_automation_run_task_for_terminal_run(
            task_registry,
            run_id=run_id,
            status=refreshed_status,
            error_message=error_message,
        )
    return None


async def ensure_automation_run_owner_task_attached(
    database_automation_runs: DatabaseAutomationRunsProtocol,
    task_registry: TaskRegistryProtocol,
    *,
    run_record: JSONDict,
) -> JSONDict:
    ensured_owner_task_id = await ensure_automation_run_owner_task(
        database_automation_runs,
        task_registry,
        run_record=run_record,
    )
    run_id = require_non_empty_str(
        run_record.get("run_id"),
        label="Automation run_id",
        build_error=StateError,
    )
    user_id = require_int(
        run_record.get("user_id"),
        label="Automation user_id",
        build_error=StateError,
        minimum=1,
    )
    refreshed_run_record = await database_automation_runs.get_run(run_id, user_id)
    if not isinstance(refreshed_run_record, dict):
        raise StateError("Automation run could not be loaded after owner task attachment.")
    resolved_run_record = refreshed_run_record
    status = require_non_empty_str(
        resolved_run_record.get("status"),
        label="Automation status",
        build_error=StateError,
    )
    owner_task_id = ensured_owner_task_id or read_automation_run_owner_task_id(resolved_run_record)
    if owner_task_id is not None and read_automation_run_owner_task_id(resolved_run_record) is None:
        normalized_run_record = dict(resolved_run_record)
        normalized_run_record["owner_task_id"] = owner_task_id
        resolved_run_record = normalized_run_record
    if _requires_owner_task_id(status) and owner_task_id is None:
        raise StateError("Active automation run is missing owner_task_id.")
    return resolved_run_record


async def mark_automation_run_task_working(
    task_registry: TaskRegistryProtocol,
    *,
    owner_task_id: str | None,
) -> None:
    normalized_owner_task_id = normalize_automation_run_owner_task_id(owner_task_id)
    if normalized_owner_task_id is None:
        return
    await mark_owned_execution_running(
        task_registry,
        owner_task_id=normalized_owner_task_id,
        status_message="Running automation run.",
    )


async def finalize_automation_run_owner_task(
    task_registry: TaskRegistryProtocol,
    *,
    owner_task_id: str | None,
    final_status: AutomationRunTaskTerminalStatus,
    error_message: str | None = None,
    error_code: int | None = None,
) -> None:
    normalized_owner_task_id = normalize_automation_run_owner_task_id(owner_task_id)
    await finalize_owned_execution_task(
        task_registry,
        owner_task_id=normalized_owner_task_id,
        final_status=final_status,
        error_code=error_code,
        error_message=error_message,
        status_message=_resolve_terminal_status_message(final_status),
    )


async def finalize_abandoned_automation_owner_task_ids(
    task_registry: TaskRegistryProtocol,
    owner_task_ids: tuple[str, ...],
    *,
    error_message: str,
) -> None:
    for owner_task_id in owner_task_ids:
        await finalize_automation_run_owner_task(
            task_registry,
            owner_task_id=owner_task_id,
            final_status="abandoned",
            error_message=error_message,
        )


async def finalize_created_automation_run_task_for_terminal_run(
    task_registry: TaskRegistryProtocol,
    *,
    run_id: str,
    status: str,
    error_message: str,
) -> None:
    await finalize_automation_run_owner_task(
        task_registry,
        owner_task_id=run_id,
        final_status=_resolve_terminal_status(status),
        error_message=error_message,
    )

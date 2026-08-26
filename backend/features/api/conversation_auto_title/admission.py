"""SoAI - Auto-title admission and settlement gating [backend/features/api/conversation_auto_title/admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exceptions import StateError
from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from core.validation.integers import is_non_negative_strict_int, is_strict_int
from features.assistant_timeline.assistant_timeline_terminal_support import (
    wait_for_task_terminal_state,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "REASON_ORCHESTRATOR_BACKLOG",
    "REASON_ORIGINATING_TASK_UNSETTLED",
    "AutoTitleAdmissionResult",
    "await_auto_title_admission",
    "await_orchestrator_idle",
    "orchestrator_is_idle",
)

_ADMISSION_TIMEOUT_MS = 4000
_ADMISSION_POLL_INTERVAL_S = SHORT_POLL_INTERVAL_SEC
REASON_ORCHESTRATOR_BACKLOG = "orchestrator_backlog"
REASON_ORIGINATING_TASK_UNSETTLED = "originating_task_unsettled"


@dataclass(frozen=True, slots=True)
class AutoTitleAdmissionResult:
    admitted: bool
    reason: str | None


async def orchestrator_is_idle(api_dependencies: ApiDependencies) -> bool:
    status = await api_dependencies.orchestrator_control.get_status()
    snapshot = _read_orchestrator_backlog_snapshot(status)
    if snapshot is None:
        return False
    return (
        snapshot.queued_tasks_count == 0
        and snapshot.pending_tasks_count == 0
        and snapshot.total_backlog_size == 0
    )


async def await_auto_title_admission(
    *,
    api_dependencies: ApiDependencies,
    originating_task_id: str,
) -> AutoTitleAdmissionResult:
    normalized_task_id = originating_task_id.strip()
    if not normalized_task_id:
        raise StateError("Auto-title generation requires an originating task id.")
    deadline = deadline_after(float(_ADMISSION_TIMEOUT_MS) / 1000.0)
    task = await wait_for_task_terminal_state(
        task_id=normalized_task_id,
        task_lookup=lambda task_id: api_dependencies.task_registry.get(
            task_id,
            force_refresh=True,
        ),
        timeout_ms=_ADMISSION_TIMEOUT_MS,
    )
    if task is None or task.status.is_terminal():
        return await await_orchestrator_idle(
            api_dependencies=api_dependencies,
            deadline=deadline,
        )
    return AutoTitleAdmissionResult(
        admitted=False,
        reason=REASON_ORIGINATING_TASK_UNSETTLED,
    )


async def await_orchestrator_idle(
    *,
    api_dependencies: ApiDependencies,
    deadline: MonotonicDeadline | None = None,
) -> AutoTitleAdmissionResult:
    resolved_deadline = deadline or deadline_after(float(_ADMISSION_TIMEOUT_MS) / 1000.0)
    while True:
        status = await api_dependencies.orchestrator_control.get_status()
        snapshot = _read_orchestrator_backlog_snapshot(status)
        if snapshot is None:
            return AutoTitleAdmissionResult(admitted=False, reason=REASON_ORCHESTRATOR_BACKLOG)
        if snapshot.queued_tasks_count > 0:
            return AutoTitleAdmissionResult(admitted=False, reason=REASON_ORCHESTRATOR_BACKLOG)
        if snapshot.total_backlog_size == 0:
            return AutoTitleAdmissionResult(admitted=True, reason=None)
        if snapshot.pending_tasks_count > 0:
            return AutoTitleAdmissionResult(admitted=False, reason=REASON_ORCHESTRATOR_BACKLOG)
        if resolved_deadline.expired():
            break
        await asyncio.sleep(_ADMISSION_POLL_INTERVAL_S)
    return AutoTitleAdmissionResult(admitted=False, reason=REASON_ORCHESTRATOR_BACKLOG)


@dataclass(frozen=True, slots=True)
class OrchestratorBacklogSnapshot:
    queued_tasks_count: int
    pending_tasks_count: int
    total_backlog_size: int


def _read_orchestrator_backlog_snapshot(status: JSONDict) -> OrchestratorBacklogSnapshot | None:
    if not isinstance(status, dict):
        return None
    if status.get("status") != "OPERATIONAL":
        return None
    queued_value = status.get("queued_tasks_count")
    pending_value = status.get("pending_tasks_by_uid")
    backlog_value = status.get("total_backlog_size")
    if not is_strict_int(queued_value):
        return None
    if not isinstance(pending_value, dict):
        return None
    if not is_strict_int(backlog_value):
        return None
    if queued_value < 0 or backlog_value < 0:
        return None
    pending_tasks_count = 0
    for value in pending_value.values():
        if not is_non_negative_strict_int(value):
            return None
        pending_tasks_count += value
    return OrchestratorBacklogSnapshot(
        queued_tasks_count=queued_value,
        pending_tasks_count=pending_tasks_count,
        total_backlog_size=backlog_value,
    )

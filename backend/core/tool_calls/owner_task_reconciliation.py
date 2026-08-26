"""SoAI - Tool call owner task terminal reconciliation [backend/core/tool_calls/owner_task_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.execution.owned_execution_tasks import (
    finalize_owned_execution_task,
    request_owned_execution_cancellation,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.types.json import JSONDict

__all__ = (
    "ToolCallOwnerTaskTerminalReconciliation",
    "reconcile_tool_call_owner_task_terminal_state",
    "reconcile_tool_call_owner_task_terminal_states",
)

OWNER_TASK_TERMINAL_WAIT_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class ToolCallOwnerTaskTerminalReconciliation:
    tool_call: JSONDict
    terminal_status: str
    terminal_message: str | None


def _read_owner_task_id(tool_call: JSONDict) -> str | None:
    value = tool_call.get("owner_task_id")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _status_message(status: str) -> str:
    if status == TOOL_CALL_STATUS_COMPLETED:
        return "Completed"
    if status == TOOL_CALL_STATUS_CANCELLED:
        return "Cancelled"
    return "Failed"


async def _wait_for_terminal_task(
    task_registry: TaskRegistryLifecycleView,
    *,
    owner_task_id: str,
) -> None:
    completion_event = await task_registry.ensure_completion_event(
        owner_task_id,
        set_if_terminal=False,
    )
    try:
        task = await task_registry.get(owner_task_id, force_refresh=True)
        if task is None or task.status.is_terminal():
            return
        await asyncio.wait_for(
            completion_event.wait(),
            timeout=OWNER_TASK_TERMINAL_WAIT_SECONDS,
        )
    except TimeoutError:
        return
    finally:
        await task_registry.release_completion_event(owner_task_id)


async def reconcile_tool_call_owner_task_terminal_state(
    *,
    task_registry: TaskRegistryLifecycleView,
    tool_call: JSONDict,
    terminal_status: str,
    terminal_message: str | None,
) -> None:
    owner_task_id = _read_owner_task_id(tool_call)
    if owner_task_id is None:
        return
    task = await task_registry.get(owner_task_id, force_refresh=True)
    if task is None or task.status.is_terminal():
        return
    normalized_status = terminal_status.strip().lower()
    if normalized_status in (TOOL_CALL_STATUS_CANCELLED, TOOL_CALL_STATUS_ERROR):
        await request_owned_execution_cancellation(
            task_registry,
            owner_task_id=owner_task_id,
            reason=terminal_message or "Tool call finalized.",
        )
        await _wait_for_terminal_task(task_registry, owner_task_id=owner_task_id)
        task = await task_registry.get(owner_task_id, force_refresh=True)
        if task is None or task.status.is_terminal():
            return
    final_status = (
        normalized_status
        if normalized_status in (TOOL_CALL_STATUS_COMPLETED, TOOL_CALL_STATUS_CANCELLED)
        else TOOL_CALL_STATUS_ERROR
    )
    await finalize_owned_execution_task(
        task_registry,
        owner_task_id=owner_task_id,
        final_status=final_status,
        status_message=_status_message(final_status),
        error_message=terminal_message if final_status != TOOL_CALL_STATUS_COMPLETED else None,
    )


async def reconcile_tool_call_owner_task_terminal_states(
    *,
    task_registry: TaskRegistryLifecycleView,
    reconciliations: Sequence[ToolCallOwnerTaskTerminalReconciliation],
) -> None:
    if not reconciliations:
        return
    tasks = [
        reconcile_tool_call_owner_task_terminal_state(
            task_registry=task_registry,
            tool_call=reconciliation.tool_call,
            terminal_status=reconciliation.terminal_status,
            terminal_message=reconciliation.terminal_message,
        )
        for reconciliation in reconciliations
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result

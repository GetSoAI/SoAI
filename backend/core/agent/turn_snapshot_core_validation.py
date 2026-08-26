"""SoAI - Agent turn snapshot core validation helpers [backend/core/agent/turn_snapshot_core_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_ALL_STATUSES,
    AGENT_TURN_STATUS_RUNNING,
    AGENT_TURN_TERMINAL_STATUSES,
)
from core.agent.turn_scope_values import TURN_SCOPE_ALL, TURN_SCOPE_ROOT
from core.agent.turn_timing_validation import has_valid_execution_timing
from core.agent_mode import is_agent_mode, is_plan_or_execute_agent_mode

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "has_valid_turn_snapshot_core",
    "mode_matches_turn_scope",
)


def has_valid_turn_snapshot_core(
    *,
    conv_id: str | None,
    turn_id: str | None,
    turn_scope: str | None,
    status: str | None,
    mode: str | None,
    execution_token: str | None,
    server_boot_id: str | None,
    user_id: int | None,
    max_iterations: int | None,
    iteration_index: int | None,
    sequence: int | None,
    todo_revision: int | None,
    started_at_ms: int | None,
    updated_at_ms: int | None,
    finished_at_ms: int | None,
    reached_max_iterations: bool | None,
    tool_calls: list[JSONDict] | None,
    tool_results: list[JSONValue] | None,
    activities: list[JSONDict] | None,
    todo: list[JSONDict] | None,
) -> bool:
    if conv_id is None or turn_id is None:
        return False
    if turn_scope not in TURN_SCOPE_ALL:
        return False
    if status not in AGENT_TURN_ALL_STATUSES:
        return False
    if mode is None or not mode_matches_turn_scope(turn_scope=turn_scope, mode=mode):
        return False
    if execution_token is None or server_boot_id is None:
        return False
    if user_id is None or max_iterations is None or iteration_index is None:
        return False
    if sequence is None or todo_revision is None:
        return False
    if started_at_ms is None or updated_at_ms is None or reached_max_iterations is None:
        return False
    if tool_calls is None or tool_results is None or activities is None or todo is None:
        return False
    if len(tool_results) > len(tool_calls):
        return False
    return has_valid_execution_timing(
        status=status,
        running_status=AGENT_TURN_STATUS_RUNNING,
        terminal_statuses=AGENT_TURN_TERMINAL_STATUSES,
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
    )


def mode_matches_turn_scope(*, turn_scope: str, mode: str | None) -> bool:
    if mode is None:
        return False
    if turn_scope == TURN_SCOPE_ROOT:
        return is_agent_mode(mode)
    return is_plan_or_execute_agent_mode(mode)

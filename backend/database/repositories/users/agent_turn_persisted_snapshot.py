"""SoAI - Persisted agent turn snapshot comparison [backend/database/repositories/users/agent_turn_persisted_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.turn_record_fields import TurnStateHeader
from core.agent.turn_write_conflicts import (
    TURN_WRITE_STALE_ITERATION_MESSAGE,
    TURN_WRITE_STALE_SEQUENCE_MESSAGE,
    TURN_WRITE_STALE_UPDATE_MESSAGE,
    AgentTurnStaleProgressError,
)
from core.database.requests import WriteAgentTurnStateRequest
from core.errors.exceptions import ValidationError
from database.core.sqlite_numbers import coerce_int_from_sqlite
from database.repositories.users.agent_turn_text_normalization import (
    normalize_agent_turn_optional_text,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow

    type ComparableTurnValue = bool | int | str | None

__all__ = (
    "PersistedTurnSnapshot",
    "read_persisted_turn_snapshot",
    "validate_lineage_matches",
    "validate_monotonic_progress",
    "validate_terminal_replay_matches",
)


@dataclass(frozen=True, slots=True)
class PersistedTurnProgressSnapshot:
    updated_at_ms: int
    iteration_index: int
    sequence: int


@dataclass(frozen=True, slots=True)
class PersistedTurnTerminalSnapshot:
    status: str
    reached_max_iterations: bool
    error_message: str | None
    error_type: str | None
    mode: str
    max_iterations: int
    turn_cancellation_id: str | None
    active_inference_cancellation_id: str | None
    assistant_text: str | None
    tool_calls_json: str
    tool_results_json: str
    activities_json: str
    token_usage_json: str | None
    todo_revision: int
    todo_explanation: str | None
    todo_json: str


@dataclass(frozen=True, slots=True)
class PersistedTurnSnapshot:
    execution_token: str
    status: str
    lineage: TurnStateHeader
    progress: PersistedTurnProgressSnapshot
    terminal: PersistedTurnTerminalSnapshot


@dataclass(frozen=True, slots=True)
class TurnFieldComparison:
    field_name: str
    persisted_value: ComparableTurnValue
    request_value: ComparableTurnValue
    skip_when_request_none: bool = False


def _read_nonnegative_int(row: SQLiteRow, field_name: str, default: int) -> int:
    return max(default, coerce_int_from_sqlite(row.get(field_name)) or default)


def read_persisted_turn_snapshot(row: SQLiteRow) -> PersistedTurnSnapshot:
    status = str(row.get("status") or "").strip()
    lineage = TurnStateHeader(
        turn_scope=str(row.get("turn_scope") or "").strip(),
        parent_turn_id=normalize_agent_turn_optional_text(row.get("parent_turn_id")),
        parent_tool_call_id=normalize_agent_turn_optional_text(row.get("parent_tool_call_id")),
        parent_iteration_index=coerce_int_from_sqlite(row.get("parent_iteration_index")),
        display_name=normalize_agent_turn_optional_text(row.get("display_name")),
        requested_model=normalize_agent_turn_optional_text(row.get("requested_model")),
        owner_task_id=normalize_agent_turn_optional_text(row.get("owner_task_id")),
    )
    progress = PersistedTurnProgressSnapshot(
        updated_at_ms=_read_nonnegative_int(row, "updated_at_ms", 0),
        iteration_index=_read_nonnegative_int(row, "iteration_index", 0),
        sequence=_read_nonnegative_int(row, "sequence", 0),
    )
    terminal = PersistedTurnTerminalSnapshot(
        status=status,
        reached_max_iterations=(coerce_int_from_sqlite(row.get("reached_max_iterations")) or 0)
        == 1,
        error_message=normalize_agent_turn_optional_text(row.get("error_message")),
        error_type=normalize_agent_turn_optional_text(row.get("error_type")),
        mode=str(row.get("mode") or "").strip(),
        max_iterations=_read_nonnegative_int(row, "max_iterations", 1),
        turn_cancellation_id=normalize_agent_turn_optional_text(row.get("turn_cancellation_id")),
        active_inference_cancellation_id=normalize_agent_turn_optional_text(
            row.get("active_inference_cancellation_id"),
        ),
        assistant_text=normalize_agent_turn_optional_text(row.get("assistant_text")),
        tool_calls_json=str(row.get("tool_calls_json") or ""),
        tool_results_json=str(row.get("tool_results_json") or ""),
        activities_json=str(row.get("activities_json") or ""),
        token_usage_json=normalize_agent_turn_optional_text(row.get("token_usage_json")),
        todo_revision=_read_nonnegative_int(row, "todo_revision", 0),
        todo_explanation=normalize_agent_turn_optional_text(row.get("todo_explanation")),
        todo_json=str(row.get("todo_json") or ""),
    )
    return PersistedTurnSnapshot(
        execution_token=str(row.get("execution_token") or "").strip(),
        status=status,
        lineage=lineage,
        progress=progress,
        terminal=terminal,
    )


def validate_monotonic_progress(
    persisted: PersistedTurnProgressSnapshot,
    request: WriteAgentTurnStateRequest,
) -> None:
    if int(request.updated_at_ms) < persisted.updated_at_ms:
        raise AgentTurnStaleProgressError(TURN_WRITE_STALE_UPDATE_MESSAGE)
    if int(request.iteration_index) < persisted.iteration_index:
        raise AgentTurnStaleProgressError(TURN_WRITE_STALE_ITERATION_MESSAGE)
    if int(request.sequence) < persisted.sequence:
        raise AgentTurnStaleProgressError(TURN_WRITE_STALE_SEQUENCE_MESSAGE)


def validate_lineage_matches(
    persisted: TurnStateHeader,
    request: WriteAgentTurnStateRequest,
    *,
    message_prefix: str,
) -> None:
    comparisons = (
        TurnFieldComparison("turn_scope", persisted.turn_scope, request.turn_scope),
        TurnFieldComparison(
            "parent_turn_id",
            persisted.parent_turn_id,
            normalize_agent_turn_optional_text(request.parent_turn_id),
        ),
        TurnFieldComparison(
            "parent_tool_call_id",
            persisted.parent_tool_call_id,
            normalize_agent_turn_optional_text(request.parent_tool_call_id),
        ),
        TurnFieldComparison(
            "parent_iteration_index",
            persisted.parent_iteration_index,
            request.parent_iteration_index,
        ),
        TurnFieldComparison(
            "display_name",
            persisted.display_name,
            normalize_agent_turn_optional_text(request.display_name),
        ),
        TurnFieldComparison(
            "requested_model",
            persisted.requested_model,
            normalize_agent_turn_optional_text(request.requested_model),
        ),
        TurnFieldComparison(
            "owner_task_id",
            persisted.owner_task_id,
            normalize_agent_turn_optional_text(request.owner_task_id),
        ),
    )
    _validate_field_comparisons(comparisons, message_prefix)


def validate_terminal_replay_matches(
    persisted: PersistedTurnSnapshot,
    request: WriteAgentTurnStateRequest,
) -> None:
    terminal = persisted.terminal
    comparisons = (
        TurnFieldComparison(
            "iteration_index",
            persisted.progress.iteration_index,
            request.iteration_index,
        ),
        TurnFieldComparison("sequence", persisted.progress.sequence, request.sequence),
        TurnFieldComparison(
            "reached_max_iterations",
            terminal.reached_max_iterations,
            request.reached_max_iterations,
        ),
        TurnFieldComparison(
            "error_message",
            terminal.error_message,
            normalize_agent_turn_optional_text(request.error_message),
        ),
        TurnFieldComparison(
            "error_type",
            terminal.error_type,
            normalize_agent_turn_optional_text(request.error_type),
        ),
        TurnFieldComparison("mode", terminal.mode, request.mode),
        TurnFieldComparison("turn_scope", persisted.lineage.turn_scope, request.turn_scope),
        TurnFieldComparison("max_iterations", terminal.max_iterations, int(request.max_iterations)),
        TurnFieldComparison(
            "turn_cancellation_id",
            terminal.turn_cancellation_id,
            normalize_agent_turn_optional_text(request.turn_cancellation_id),
        ),
        TurnFieldComparison(
            "active_inference_cancellation_id",
            terminal.active_inference_cancellation_id,
            normalize_agent_turn_optional_text(request.active_inference_cancellation_id),
        ),
        TurnFieldComparison(
            "assistant_text",
            terminal.assistant_text,
            normalize_agent_turn_optional_text(request.assistant_text),
        ),
        TurnFieldComparison("tool_calls_json", terminal.tool_calls_json, request.tool_calls_json),
        TurnFieldComparison(
            "tool_results_json",
            terminal.tool_results_json,
            request.tool_results_json,
        ),
        TurnFieldComparison("activities_json", terminal.activities_json, request.activities_json),
        TurnFieldComparison(
            "token_usage_json",
            terminal.token_usage_json,
            normalize_agent_turn_optional_text(request.token_usage_json),
            skip_when_request_none=True,
        ),
        TurnFieldComparison("todo_revision", terminal.todo_revision, int(request.todo_revision)),
        TurnFieldComparison(
            "todo_explanation",
            terminal.todo_explanation,
            normalize_agent_turn_optional_text(request.todo_explanation),
        ),
        TurnFieldComparison("todo_json", terminal.todo_json, request.todo_json),
    )
    _validate_field_comparisons(comparisons, "Agent turn terminal ")
    validate_lineage_matches(persisted.lineage, request, message_prefix="Agent turn terminal ")


def _validate_field_comparisons(
    comparisons: tuple[TurnFieldComparison, ...],
    message_prefix: str,
) -> None:
    for comparison in comparisons:
        if comparison.skip_when_request_none and comparison.request_value is None:
            continue
        if comparison.persisted_value != comparison.request_value:
            raise ValidationError(
                f"{message_prefix}{comparison.field_name} does not match persisted state.",
            )

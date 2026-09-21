"""SoAI - Agent turn row normalization [backend/database/repositories/users/agent_turn_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_ALL
from core.errors.exceptions import DatabaseError
from core.validation.record_fields import (
    require_int,
    require_non_empty_str,
    require_optional_int,
    require_optional_str,
)
from database.core.row_fields import (
    require_row_json_list,
    require_row_optional_json_object,
)
from database.core.sqlite_numbers import coerce_int_from_sqlite

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = ("format_agent_turn_row",)

FORMAT_ROW_OPERATION = "database.agent_turns.format_row"


def _build_row_error(message: str) -> DatabaseError:
    return DatabaseError(message, operation=FORMAT_ROW_OPERATION)


def _parse_optional_text(value: SQLiteValue, *, field_name: str) -> str | None:
    return require_optional_str(
        value,
        label=f"Agent turn row field '{field_name}'",
        build_error=_build_row_error,
    )


def _parse_optional_content_text(value: SQLiteValue) -> str | None:
    return value if isinstance(value, str) else None


def format_agent_turn_row(row: SQLiteRowDict | None) -> JSONDict | None:
    if not row:
        return None
    conv_id = require_non_empty_str(
        row.get("conv_id"),
        label="Agent turn row field 'conv_id'",
        build_error=_build_row_error,
    )
    turn_id = require_non_empty_str(
        row.get("turn_id"),
        label="Agent turn row field 'turn_id'",
        build_error=_build_row_error,
    )
    execution_token = require_non_empty_str(
        row.get("execution_token"),
        label="Agent turn row field 'execution_token'",
        build_error=_build_row_error,
    )
    server_boot_id = require_non_empty_str(
        row.get("server_boot_id"),
        label="Agent turn row field 'server_boot_id'",
        build_error=_build_row_error,
    )
    status = require_non_empty_str(
        row.get("status"),
        label="Agent turn row field 'status'",
        build_error=_build_row_error,
    )
    turn_scope = require_non_empty_str(
        row.get("turn_scope"),
        label="Agent turn row field 'turn_scope'",
        build_error=_build_row_error,
    )
    if turn_scope not in TURN_SCOPE_ALL:
        raise _build_row_error("Agent turn row has invalid turn_scope.")
    mode = require_non_empty_str(
        row.get("mode"),
        label="Agent turn row field 'mode'",
        build_error=_build_row_error,
    )
    user_id = require_int(
        row.get("user_id"),
        label="Agent turn row field 'user_id'",
        build_error=_build_row_error,
        minimum=1,
    )
    max_iterations = require_int(
        row.get("max_iterations"),
        label="Agent turn row field 'max_iterations'",
        build_error=_build_row_error,
        minimum=1,
    )
    iteration_index = require_int(
        row.get("iteration_index"),
        label="Agent turn row field 'iteration_index'",
        build_error=_build_row_error,
        minimum=0,
    )
    sequence = require_int(
        row.get("sequence"),
        label="Agent turn row field 'sequence'",
        build_error=_build_row_error,
        minimum=0,
    )
    parent_iteration_index = require_optional_int(
        row.get("parent_iteration_index"),
        label="Agent turn row field 'parent_iteration_index'",
        build_error=_build_row_error,
        minimum=0,
    )
    todo_revision = require_int(
        row.get("todo_revision"),
        label="Agent turn row field 'todo_revision'",
        build_error=_build_row_error,
        minimum=0,
    )
    started_at_ms = require_int(
        row.get("started_at_ms"),
        label="Agent turn row field 'started_at_ms'",
        build_error=_build_row_error,
        minimum=0,
    )
    updated_at_ms = require_int(
        row.get("updated_at_ms"),
        label="Agent turn row field 'updated_at_ms'",
        build_error=_build_row_error,
        minimum=0,
    )
    finished_at_ms = coerce_int_from_sqlite(row.get("finished_at_ms"))
    tool_calls = require_row_json_list(
        row.get("tool_calls_json"),
        label="Agent turn row has invalid tool_calls_json.",
        build_error=_build_row_error,
    )
    tool_results = require_row_json_list(
        row.get("tool_results_json"),
        label="Agent turn row has invalid tool_results_json.",
        build_error=_build_row_error,
    )
    activities = require_row_json_list(
        row.get("activities_json"),
        label="Agent turn row has invalid activities_json.",
        build_error=_build_row_error,
    )
    todo = require_row_json_list(
        row.get("todo_json"),
        label="Agent turn row has invalid todo_json.",
        build_error=_build_row_error,
    )
    reached_max_iterations_value = coerce_int_from_sqlite(row.get("reached_max_iterations"))
    if reached_max_iterations_value not in (0, 1):
        raise _build_row_error("Agent turn row has invalid reached_max_iterations.")
    return {
        "conv_id": conv_id,
        "user_id": int(user_id),
        "turn_id": turn_id,
        "turn_scope": turn_scope,
        "parent_turn_id": _parse_optional_text(
            row.get("parent_turn_id"),
            field_name="parent_turn_id",
        ),
        "parent_tool_call_id": _parse_optional_text(
            row.get("parent_tool_call_id"),
            field_name="parent_tool_call_id",
        ),
        "parent_iteration_index": parent_iteration_index,
        "display_name": _parse_optional_text(row.get("display_name"), field_name="display_name"),
        "requested_model": _parse_optional_text(
            row.get("requested_model"),
            field_name="requested_model",
        ),
        "owner_task_id": _parse_optional_text(row.get("owner_task_id"), field_name="owner_task_id"),
        "execution_token": execution_token,
        "server_boot_id": server_boot_id,
        "status": status,
        "mode": mode,
        "max_iterations": int(max_iterations),
        "iteration_index": int(iteration_index),
        "sequence": int(sequence),
        "turn_cancellation_id": _parse_optional_text(
            row.get("turn_cancellation_id"),
            field_name="turn_cancellation_id",
        ),
        "active_inference_cancellation_id": _parse_optional_text(
            row.get("active_inference_cancellation_id"),
            field_name="active_inference_cancellation_id",
        ),
        "assistant_text": (
            row.get("assistant_text") if isinstance(row.get("assistant_text"), str) else None
        ),
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "activities": activities,
        "reached_max_iterations": reached_max_iterations_value == 1,
        "error_message": _parse_optional_content_text(row.get("error_message")),
        "error_type": _parse_optional_text(row.get("error_type"), field_name="error_type"),
        "token_usage": require_row_optional_json_object(
            row.get("token_usage_json"),
            label="Agent turn row has invalid token_usage_json.",
            build_error=_build_row_error,
        ),
        "todo_revision": int(todo_revision),
        "todo_explanation": _parse_optional_content_text(row.get("todo_explanation")),
        "todo": todo,
        "manual_regeneration_request": require_row_optional_json_object(
            row.get("manual_regeneration_request_json"),
            label="Agent turn row has invalid manual_regeneration_request_json.",
            build_error=_build_row_error,
        ),
        "manual_regeneration_accepted_revision": require_optional_int(
            row.get("manual_regeneration_accepted_revision"),
            label="Agent turn row field 'manual_regeneration_accepted_revision'",
            build_error=_build_row_error,
            minimum=0,
        ),
        "started_at_ms": started_at_ms,
        "updated_at_ms": updated_at_ms,
        "finished_at_ms": int(finished_at_ms) if finished_at_ms is not None else None,
    }

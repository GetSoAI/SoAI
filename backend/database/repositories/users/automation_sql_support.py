"""SoAI - Shared automation SQL support [backend/database/repositories/users/automation_sql_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.users.user_id import is_strict_user_id
from database.core.json_codec import (
    serialize_required_json_list_field,
    serialize_required_json_object_field,
)
from database.core.query_execution import sync_fetch_one_as_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = (
    "automation_select_sql",
    "build_run_snapshot_json_strings",
    "fetch_run_row_by_id",
    "insert_automation_run",
    "run_select_sql",
    "run_summary_select_sql",
)

_RUN_SELECT_SQL = """
    SELECT
        r.id AS run_id,
        r.automation_id,
        r.user_id,
        r.owner_task_id,
        r.scheduled_at_ms AS scheduled_at_ms,
        r.started_at_ms AS started_at_actual_ms,
        r.finished_at_ms AS finished_at_ms,
        r.status,
        r.status_message,
        r.conv_id,
    r.result_excerpt,
    r.turns_snapshot,
    r.model_settings_snapshot,
    r.limits_snapshot,
    COALESCE(r.color_snapshot, a.color) AS color,
    a.title,
    a.enabled
FROM automation_runs AS r
LEFT JOIN automations AS a ON a.id = r.automation_id
"""

_RUN_SUMMARY_SELECT_SQL = """
    SELECT
        r.id AS run_id,
        r.automation_id,
        r.user_id,
        r.owner_task_id,
        r.scheduled_at_ms AS scheduled_at_ms,
        r.started_at_ms AS started_at_actual_ms,
        r.finished_at_ms AS finished_at_ms,
        r.status,
        r.status_message,
        r.conv_id,
    r.result_excerpt,
    COALESCE(r.color_snapshot, a.color) AS color,
    a.title,
    a.enabled
FROM automation_runs AS r
LEFT JOIN automations AS a ON a.id = r.automation_id
"""


def automation_select_sql() -> str:
    return """
    SELECT
        id,
        user_id,
        title,
        enabled,
        color,
        created_at_ms,
        last_modified_at_ms,
        timezone,
        start_local,
        recurrence,
        next_run_at_ms,
        model_settings,
        turns_json AS turns,
        max_turns,
        max_turn_chars,
        max_run_minutes
    FROM automations
    """


def run_select_sql() -> str:
    return _RUN_SELECT_SQL


def run_summary_select_sql() -> str:
    return _RUN_SUMMARY_SELECT_SQL


def fetch_run_row_by_id(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    user_id: int | None = None,
) -> SQLiteRowDict | None:
    sql = f"{_RUN_SELECT_SQL} WHERE r.id = ?"
    params: tuple[SQLiteValue, ...]
    if user_id is None:
        params = (run_id,)
    else:
        sql = f"{sql} AND r.user_id = ?"
        params = (run_id, user_id)
    cursor = conn.execute(sql, params)
    return sync_fetch_one_as_dict(cursor)


def build_run_snapshot_json_strings(automation_record: JSONDict) -> tuple[str, str, str]:
    turns_value = automation_record.get("turns")
    model_settings_value = automation_record.get("model_settings")
    interactive_tool_approval_value = automation_record.get("interactive_tool_approval")
    max_turns_value = automation_record.get("max_turns")
    max_turn_chars_value = automation_record.get("max_turn_chars")
    max_run_minutes_value = automation_record.get("max_run_minutes")
    if not isinstance(turns_value, list):
        raise ValueError("Automation turns are invalid.")
    if not isinstance(model_settings_value, dict):
        raise ValueError("Automation model_settings are invalid.")
    if not isinstance(interactive_tool_approval_value, bool):
        raise ValueError("Automation interactive_tool_approval is invalid.")
    if (
        not isinstance(max_turns_value, int)
        or not isinstance(max_turn_chars_value, int)
        or not isinstance(max_run_minutes_value, int)
    ):
        raise ValueError("Automation limits are invalid.")
    normalized_model_settings = dict(model_settings_value)
    agent_value = normalized_model_settings.get("agent")
    agent = agent_value if isinstance(agent_value, dict) else {}
    normalized_agent = dict(agent)
    normalized_agent["interactive_tool_approval"] = interactive_tool_approval_value
    normalized_model_settings["agent"] = normalized_agent
    turns_snapshot = serialize_required_json_list_field(
        turns_value,
        error_message="Automation turns are invalid.",
    )
    model_settings_snapshot = serialize_required_json_object_field(
        normalized_model_settings,
        error_message="Automation model_settings are invalid.",
    )
    limits_snapshot = serialize_required_json_object_field(
        {
            "max_turns": max_turns_value,
            "max_turn_chars": max_turn_chars_value,
            "max_run_minutes": max_run_minutes_value,
        },
        error_message="Automation limits are invalid.",
    )
    return (turns_snapshot, model_settings_snapshot, limits_snapshot)


def insert_automation_run(
    conn: sqlite3.Connection,
    *,
    automation_record: JSONDict,
    run_id: str,
    scheduled_at_ms: int,
    status: str,
    status_message: str | None,
    finished_at_ms: int | None,
) -> None:
    automation_id_value = automation_record.get("id")
    user_id_value = automation_record.get("user_id")
    color_value = automation_record.get("color")
    if not isinstance(automation_id_value, str) or not automation_id_value.strip():
        raise ValueError("Automation id is invalid.")
    if not is_strict_user_id(user_id_value):
        raise ValueError("Automation user_id is invalid.")
    color = color_value if isinstance(color_value, str) and color_value.strip() else None
    turns_snapshot, model_settings_snapshot, limits_snapshot = build_run_snapshot_json_strings(
        automation_record,
    )
    conn.execute(
        """
        INSERT INTO automation_runs (
            id,
            automation_id,
            user_id,
            owner_task_id,
            scheduled_at_ms,
            started_at_ms,
            finished_at_ms,
            status,
            status_message,
            conv_id,
            result_excerpt,
            turns_snapshot,
            model_settings_snapshot,
            limits_snapshot,
            color_snapshot
        ) VALUES (?, ?, ?, NULL, ?, NULL, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
        """,
        (
            run_id,
            automation_id_value,
            user_id_value,
            int(scheduled_at_ms),
            finished_at_ms,
            status,
            status_message,
            turns_snapshot,
            model_settings_snapshot,
            limits_snapshot,
            color,
        ),
    )

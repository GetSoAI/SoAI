"""SoAI - Context compaction metric event persistence [backend/database/repositories/users/context_compaction_metric_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.tool_calls.context_compaction_metrics import (
    resolve_context_compaction_metric_tokens_saved,
)
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.row_fields import (
    coerce_row_optional_non_negative_int,
    require_row_epoch_ms,
    require_row_non_empty_str,
    require_row_non_negative_int,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = (
    "get_context_compaction_metric_totals_query",
    "sync_delete_context_compaction_metric_events_for_assistant_turn",
    "sync_delete_context_compaction_metric_events_for_conversation",
    "sync_get_context_compaction_metric_totals",
    "sync_reconcile_context_compaction_metric_events",
    "sync_record_context_compaction_metric_event",
)


_TOTALS_SQL = """
    SELECT
        COALESCE(
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END),
            0
        ) AS completed_count,
        COALESCE(SUM(tokens_saved), 0) AS tokens_saved
    FROM webui_context_compaction_metric_events
    """


def _require_json_metric_value(value: SQLiteValue, label: str) -> JSONValue:
    if isinstance(value, bytes):
        raise StateError(f"{label} must not be bytes.")
    return value


def _build_metric_payload_from_sqlite_row(row: SQLiteRowDict) -> JSONDict:
    return {
        "id": _require_json_metric_value(row.get("id"), "Context compaction metric id"),
        "conv_id": _require_json_metric_value(
            row.get("conv_id"),
            "Context compaction metric conv_id",
        ),
        "assistant_turn_at_ms": _require_json_metric_value(
            row.get("assistant_turn_at_ms"),
            "Context compaction metric assistant_turn_at_ms",
        ),
        "model_variant_index": _require_json_metric_value(
            row.get("model_variant_index"),
            "Context compaction metric model_variant_index",
        ),
        "tool_name": _require_json_metric_value(
            row.get("tool_name"),
            "Context compaction metric tool_name",
        ),
        "result": _require_json_metric_value(row.get("result"), "Context compaction metric result"),
        "status": _require_json_metric_value(row.get("status"), "Context compaction metric status"),
        "completed_at_ms": _require_json_metric_value(
            row.get("completed_at_ms"),
            "Context compaction metric completed_at_ms",
        ),
    }


def _format_metric_row(row: JSONDict) -> JSONDict | None:
    tokens_saved = resolve_context_compaction_metric_tokens_saved(
        {
            "tool_name": row.get("tool_name"),
            "status": row.get("status"),
            "result": row.get("result"),
        },
    )
    if tokens_saved is None:
        return None
    return {
        "storage_call_id": require_row_non_empty_str(
            row.get("id"),
            label="Context compaction metric storage_call_id",
            build_error=StateError,
        ),
        "conv_id": require_row_non_empty_str(
            row.get("conv_id"),
            label="Context compaction metric conv_id",
            build_error=StateError,
        ),
        "assistant_turn_at_ms": require_row_epoch_ms(
            row.get("assistant_turn_at_ms"),
            label="Context compaction metric assistant_turn_at_ms",
            build_error=StateError,
        ),
        "model_variant_index": require_row_non_negative_int(
            row.get("model_variant_index"),
            label="Context compaction metric model_variant_index",
            build_error=StateError,
        ),
        "status": require_row_non_empty_str(
            row.get("status"),
            label="Context compaction metric status",
            build_error=StateError,
        ),
        "tokens_saved": tokens_saved,
        "recorded_at_ms": (
            coerce_row_optional_non_negative_int(row.get("completed_at_ms")) or epoch_ms()
        ),
    }


def sync_record_context_compaction_metric_event(
    conn: sqlite3.Connection,
    tool_call: JSONDict | None,
) -> None:
    if tool_call is None:
        return
    metric_row = _format_metric_row(tool_call)
    if metric_row is None:
        return
    conn.execute(
        """
        INSERT INTO webui_context_compaction_metric_events (
            storage_call_id, conv_id, assistant_turn_at_ms, model_variant_index, status,
            tokens_saved, recorded_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(storage_call_id) DO UPDATE SET
            conv_id = excluded.conv_id,
            assistant_turn_at_ms = excluded.assistant_turn_at_ms,
            model_variant_index = excluded.model_variant_index,
            status = excluded.status,
            tokens_saved = CASE
                WHEN excluded.tokens_saved > tokens_saved THEN excluded.tokens_saved
                ELSE tokens_saved
            END,
            recorded_at_ms = CASE
                WHEN excluded.recorded_at_ms < recorded_at_ms THEN excluded.recorded_at_ms
                ELSE recorded_at_ms
            END
        """,
        (
            metric_row["storage_call_id"],
            metric_row["conv_id"],
            metric_row["assistant_turn_at_ms"],
            metric_row["model_variant_index"],
            metric_row["status"],
            metric_row["tokens_saved"],
            metric_row["recorded_at_ms"],
        ),
    )


def sync_delete_context_compaction_metric_events_for_conversation(
    conn: sqlite3.Connection,
    conv_id: str,
) -> None:
    conn.execute(
        "DELETE FROM webui_context_compaction_metric_events WHERE conv_id = ?",
        (conv_id,),
    )


def sync_delete_context_compaction_metric_events_for_assistant_turn(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> None:
    conn.execute(
        """
        DELETE FROM webui_context_compaction_metric_events
        WHERE storage_call_id IN (
            SELECT id
            FROM webui_chat_tool_calls
            WHERE conv_id = ?
              AND assistant_turn_at_ms = ?
              AND model_variant_index = ?
        )
        """,
        (conv_id, int(assistant_turn_at_ms), int(model_variant_index)),
    )


def sync_reconcile_context_compaction_metric_events(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        DELETE FROM webui_context_compaction_metric_events
        WHERE storage_call_id NOT IN (
            SELECT id
            FROM webui_chat_tool_calls
            WHERE tool_name = ?
              AND status IN ('completed', 'cancelled', 'error')
        )
        """,
        (CONTEXT_COMPACTION_TOOL_NAME,),
    )
    cursor = conn.execute(
        """
        SELECT
            id,
            conv_id,
            assistant_turn_at_ms,
            model_variant_index,
            tool_name,
            tool_result AS result,
            status,
            completed_at_ms
        FROM webui_chat_tool_calls
        WHERE tool_name = ?
          AND status IN ('completed', 'cancelled', 'error')
        ORDER BY completed_at_ms ASC, created_at_ms ASC, id ASC
        """,
        (CONTEXT_COMPACTION_TOOL_NAME,),
    )
    for row in cursor.fetchall():
        sync_record_context_compaction_metric_event(
            conn,
            _build_metric_payload_from_sqlite_row(dict(row)),
        )


def _format_context_compaction_metric_totals(row: SQLiteRowDict | None) -> JSONDict:
    if row is None:
        return {"completed_count": 0, "tokens_saved": 0}
    return {
        "completed_count": require_row_non_negative_int(
            row.get("completed_count"),
            label="Context compaction completed_count",
            build_error=StateError,
        ),
        "tokens_saved": require_row_non_negative_int(
            row.get("tokens_saved"),
            label="Context compaction tokens_saved",
            build_error=StateError,
        ),
    }


def sync_get_context_compaction_metric_totals(conn: sqlite3.Connection) -> JSONDict:
    row = sync_fetch_one_as_dict(conn.execute(_TOTALS_SQL))
    return _format_context_compaction_metric_totals(row)


async def get_context_compaction_metric_totals_query(
    database: aiosqlite.Connection,
) -> JSONDict:
    row = await query_one_to_dict(database, _TOTALS_SQL)
    return _format_context_compaction_metric_totals(row)

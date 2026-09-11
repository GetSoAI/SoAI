"""SoAI - Terminal assistant event persistence normalization [backend/database/repositories/users/message_streaming_assistant/terminal_event_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, is_json_dict
from database.core.json_codec import safe_json_deserialize_required_object

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "build_terminal_assistant_event_payload_json",
    "sync_normalize_terminal_assistant_events",
)

_TERMINAL_ACTIVITY_EVENT_TYPES = frozenset(
    (
        "loading_activity",
        "processing_activity",
        "wait_for_user_activity",
        "thinking_phase",
    ),
)
_RICH_ACTIVITY_EVENT_TYPES = frozenset(
    (
        "loading_activity",
        "processing_activity",
        "wait_for_user_activity",
    ),
)


def _resolve_terminal_status(finish_reason: str | None) -> str:
    if finish_reason == "cancelled":
        return "cancelled"
    if finish_reason == "error":
        return "error"
    return "completed"


def _resolve_duration_ms(activity: JSONDict, now_ms: int) -> int:
    duration_value = activity.get("duration_ms")
    if (
        isinstance(duration_value, int)
        and not isinstance(duration_value, bool)
        and duration_value >= 0
    ):
        return duration_value
    started_at_ms = activity.get("started_at_ms")
    if (
        isinstance(started_at_ms, int)
        and not isinstance(started_at_ms, bool)
        and started_at_ms >= 0
    ):
        return max(0, now_ms - started_at_ms)
    return 0


def _normalize_activity_payload(
    *,
    payload: JSONDict,
    event_type: str,
    terminal_status: str,
    terminal_reason: str | None,
    now_ms: int,
) -> bool:
    activity_value = payload.get(event_type)
    if not is_json_dict(activity_value):
        return False
    if activity_value.get("status") != "running":
        return False
    activity_value["status"] = terminal_status
    activity_value["duration_ms"] = _resolve_duration_ms(activity_value, now_ms)
    if event_type in _RICH_ACTIVITY_EVENT_TYPES and terminal_status != "completed":
        activity_value["reason"] = terminal_reason or terminal_status
        activity_value["error_type"] = terminal_status
    return True


def _normalize_event_payload(
    *,
    payload_json: SQLiteValue,
    event_type: str,
    terminal_status: str,
    terminal_reason: str | None,
    now_ms: int,
) -> str | None:
    payload = safe_json_deserialize_required_object(
        payload_json,
        error_message="Assistant terminal activity payload_json must decode to an object.",
    )
    changed = _normalize_activity_payload(
        payload=payload,
        event_type=event_type,
        terminal_status=terminal_status,
        terminal_reason=terminal_reason,
        now_ms=now_ms,
    )
    if not changed:
        return None
    return serialize_json_compact_stable_strict(payload)


def build_terminal_assistant_event_payload_json(
    *,
    event_type: str,
    payload_json: str,
    finish_reason: str | None,
    terminal_reason: str | None,
    now_ms: int,
) -> str:
    if event_type not in _TERMINAL_ACTIVITY_EVENT_TYPES:
        return payload_json
    normalized_payload_json = _normalize_event_payload(
        payload_json=payload_json,
        event_type=event_type,
        terminal_status=_resolve_terminal_status(finish_reason),
        terminal_reason=terminal_reason,
        now_ms=now_ms,
    )
    return payload_json if normalized_payload_json is None else normalized_payload_json


def sync_normalize_terminal_assistant_events(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    finish_reason: str | None,
    terminal_reason: str | None,
) -> None:
    now_ms = epoch_ms()
    rows = conn.execute(
        (
            "SELECT sequence, event_type, payload_json "
            "FROM webui_assistant_message_events "
            "WHERE conv_id = ? AND assistant_at_ms = ? "
            "ORDER BY sequence ASC"
        ),
        (conv_id, assistant_at_ms),
    ).fetchall()
    for sequence, event_type, payload_json in rows:
        if not isinstance(event_type, str) or event_type not in _TERMINAL_ACTIVITY_EVENT_TYPES:
            continue
        if not isinstance(payload_json, str):
            raise ValidationError("Assistant terminal activity payload_json must be text.")
        normalized_payload_json = build_terminal_assistant_event_payload_json(
            payload_json=payload_json,
            event_type=event_type,
            finish_reason=finish_reason,
            terminal_reason=terminal_reason,
            now_ms=now_ms,
        )
        if normalized_payload_json == payload_json:
            continue
        conn.execute(
            (
                "UPDATE webui_assistant_message_events "
                "SET payload_json = ? "
                "WHERE conv_id = ? AND assistant_at_ms = ? AND sequence = ?"
            ),
            (normalized_payload_json, conv_id, assistant_at_ms, sequence),
        )

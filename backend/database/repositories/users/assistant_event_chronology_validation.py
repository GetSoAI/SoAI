"""SoAI - Assistant event chronology persistence validation [backend/database/repositories/users/assistant_event_chronology_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.tool_calls.chronology import bound_optional_chronology_anchor
from core.types.json import is_json_dict
from core.validation.integers import is_strict_int
from database.core.json_codec import safe_json_deserialize_required_object

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "AssistantEventChronologyResult",
    "is_terminal_tool_event_unique_integrity_error",
    "raise_duplicate_terminal_tool_event",
    "resolve_assistant_event_chronology",
    "resolve_persisted_assistant_visible_length",
    "validate_unique_terminal_tool_event",
)

_TOOL_EVENT_TYPES = frozenset(("tool_call_created", "tool_call_started", "tool_call_completed"))
_TERMINAL_TOOL_EVENT_UNIQUE_INDEX = (
    "idx_webui_assistant_message_events_completed_tool_call_id_unique"
)
_DUPLICATE_TERMINAL_TOOL_EVENT_MESSAGE = (
    "Assistant timeline already contains a terminal tool event."
)


@dataclass(frozen=True, slots=True)
class AssistantEventChronologyResult:
    running_visible_length: int
    payload_json: str


def _resolve_terminal_tool_event_key(
    *,
    event_type: str,
    payload_json: str,
) -> str | None:
    if event_type != "tool_call_completed":
        return None
    payload = safe_json_deserialize_required_object(
        payload_json,
        error_message="Assistant event payload_json must decode to an object.",
    )
    tool_payload = payload.get("tool")
    if not is_json_dict(tool_payload):
        return None
    call_id_value = tool_payload.get("call_id")
    call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    if not call_id:
        return None
    return call_id


def validate_unique_terminal_tool_event(
    *,
    conn: sqlite3.Connection,
    conv_id: str,
    assistant_at_ms: int,
    event_type: str,
    payload_json: str,
) -> str | None:
    key = _resolve_terminal_tool_event_key(event_type=event_type, payload_json=payload_json)
    if key is None:
        return None
    existing = conn.execute(
        """
        SELECT 1
        FROM webui_assistant_message_events
        WHERE conv_id = ?
          AND assistant_at_ms = ?
          AND event_type = 'tool_call_completed'
          AND json_extract(payload_json, '$.tool.call_id') = ?
          AND json_extract(payload_json, '$.tool.call_id') IS NOT NULL
        LIMIT 1
        """,
        (conv_id, assistant_at_ms, key),
    ).fetchone()
    if existing is not None:
        raise_duplicate_terminal_tool_event()
    return key


def is_terminal_tool_event_unique_integrity_error(exception: sqlite3.IntegrityError) -> bool:
    return _TERMINAL_TOOL_EVENT_UNIQUE_INDEX in str(exception)


def raise_duplicate_terminal_tool_event() -> None:
    raise ValidationError(_DUPLICATE_TERMINAL_TOOL_EVENT_MESSAGE)


def resolve_persisted_assistant_visible_length(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
) -> int:
    value = conn.execute(
        """
        SELECT COALESCE(SUM(LENGTH(COALESCE(json_extract(payload_json, '$.delta'), ''))), 0)
        FROM webui_assistant_message_events
        WHERE conv_id = ? AND assistant_at_ms = ? AND event_type = 'assistant_text_delta'
        """,
        (conv_id, assistant_at_ms),
    ).fetchone()[0]
    if is_strict_int(value) and value >= 0:
        return value
    return 0


def _resolve_present_anchor(
    *,
    payload: JSONDict,
    key: str,
    running_visible_length: int,
    field_name: str,
    field_label: str,
) -> int | None:
    if key not in payload or payload[key] is None:
        return None
    return bound_optional_chronology_anchor(
        payload[key],
        field_name,
        upper_bound=running_visible_length,
        field_label=field_label,
    )


def _serialize_changed_payload(payload: JSONDict, original_payload_json: str, changed: bool) -> str:
    if not changed:
        return original_payload_json
    return serialize_json_compact_stable_strict(payload)


def resolve_assistant_event_chronology(
    *,
    event_type: str,
    payload_json: str,
    running_visible_length: int,
) -> AssistantEventChronologyResult:
    payload = safe_json_deserialize_required_object(
        payload_json,
        error_message="Assistant event payload_json must decode to an object.",
    )
    if event_type == "assistant_text_delta":
        delta_value = payload.get("delta")
        if isinstance(delta_value, str):
            return AssistantEventChronologyResult(
                running_visible_length=running_visible_length + len(delta_value),
                payload_json=payload_json,
            )
        return AssistantEventChronologyResult(
            running_visible_length=running_visible_length,
            payload_json=payload_json,
        )
    if event_type in _TOOL_EVENT_TYPES:
        tool_payload = payload.get("tool")
        if is_json_dict(tool_payload):
            resolved_anchor = _resolve_present_anchor(
                payload=tool_payload,
                key="content_index_before",
                running_visible_length=running_visible_length,
                field_name="tool.content_index_before",
                field_label="Assistant event",
            )
            if resolved_anchor is not None and resolved_anchor != tool_payload.get(
                "content_index_before",
            ):
                tool_payload["content_index_before"] = resolved_anchor
                return AssistantEventChronologyResult(
                    running_visible_length=running_visible_length,
                    payload_json=_serialize_changed_payload(payload, payload_json, True),
                )
        return AssistantEventChronologyResult(
            running_visible_length=running_visible_length,
            payload_json=payload_json,
        )
    if event_type == "thinking_phase":
        thinking_payload = payload.get("thinking_phase")
        if not is_json_dict(thinking_payload):
            return AssistantEventChronologyResult(
                running_visible_length=running_visible_length,
                payload_json=payload_json,
            )
        anchor_type_value = thinking_payload.get("anchor_type")
        if anchor_type_value == "position":
            resolved_anchor = _resolve_present_anchor(
                payload=thinking_payload,
                key="anchor_position",
                running_visible_length=running_visible_length,
                field_name="thinking_phase.anchor_position",
                field_label="Assistant event",
            )
            if resolved_anchor is not None and resolved_anchor != thinking_payload.get(
                "anchor_position",
            ):
                thinking_payload["anchor_position"] = resolved_anchor
                return AssistantEventChronologyResult(
                    running_visible_length=running_visible_length,
                    payload_json=_serialize_changed_payload(payload, payload_json, True),
                )
    return AssistantEventChronologyResult(
        running_visible_length=running_visible_length,
        payload_json=payload_json,
    )

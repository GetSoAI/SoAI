"""SoAI - Persisted agent turn record extraction [backend/core/agent/turn_record_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.types.json_value import coerce_json_dict
from core.validation.coercion import coerce_int_from_scalar
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "TurnStateHeader",
    "read_turn_assistant_text",
    "read_turn_id",
    "read_turn_int",
    "read_turn_optional_content_text",
    "read_turn_optional_text",
    "read_turn_payload_entries",
    "read_turn_payload_values",
    "read_turn_state_header",
    "read_turn_token_usage",
)


@dataclass(frozen=True, slots=True)
class TurnStateHeader:
    turn_scope: str
    parent_turn_id: str | None
    parent_tool_call_id: str | None
    parent_iteration_index: int | None
    display_name: str | None
    requested_model: str | None
    owner_task_id: str | None


def read_turn_id(record: JSONDict | None) -> str | None:
    if not isinstance(record, dict):
        return None
    value = record.get("turn_id")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def read_turn_int(record: JSONDict | None, field_name: str) -> int | None:
    if not isinstance(record, dict):
        return None
    return coerce_int_from_scalar(record.get(field_name))


def read_turn_optional_text(record: JSONDict | None, field_name: str) -> str | None:
    if not isinstance(record, dict):
        return None
    return coerce_optional_trimmed_str(record.get(field_name))


def read_turn_optional_content_text(record: JSONDict | None, field_name: str) -> str | None:
    if not isinstance(record, dict):
        return None
    value = record.get(field_name)
    return value if isinstance(value, str) else None


def read_turn_assistant_text(record: JSONDict | None) -> str | None:
    if not isinstance(record, dict):
        return None
    value = record.get("assistant_text")
    return value if isinstance(value, str) else None


def read_turn_payload_entries(record: JSONDict | None, field_name: str) -> list[JSONDict]:
    entries: list[JSONDict] = []
    if not isinstance(record, dict):
        return entries
    value = record.get(field_name)
    if not isinstance(value, list):
        return entries
    for entry in value:
        decoded_entry = coerce_json_dict(entry)
        if decoded_entry is not None:
            entries.append(decoded_entry)
    return entries


def read_turn_payload_values(record: JSONDict | None, field_name: str) -> list[JSONValue]:
    if not isinstance(record, dict):
        return []
    value = record.get(field_name)
    if not isinstance(value, list):
        return []
    return list(value)


def read_turn_token_usage(record: JSONDict | None) -> JSONDict | None:
    if not isinstance(record, dict):
        return None
    value = record.get("token_usage")
    if not isinstance(value, dict):
        return None
    return dict(value)


def read_turn_state_header(record: JSONDict | None) -> TurnStateHeader:
    if not isinstance(record, dict):
        return TurnStateHeader(
            turn_scope=TURN_SCOPE_ROOT,
            parent_turn_id=None,
            parent_tool_call_id=None,
            parent_iteration_index=None,
            display_name=None,
            requested_model=None,
            owner_task_id=None,
        )
    return TurnStateHeader(
        turn_scope=str(record.get("turn_scope") or TURN_SCOPE_ROOT),
        parent_turn_id=read_turn_optional_text(record, "parent_turn_id"),
        parent_tool_call_id=read_turn_optional_text(record, "parent_tool_call_id"),
        parent_iteration_index=read_turn_int(record, "parent_iteration_index"),
        display_name=read_turn_optional_text(record, "display_name"),
        requested_model=read_turn_optional_text(record, "requested_model"),
        owner_task_id=read_turn_optional_text(record, "owner_task_id"),
    )

"""SoAI - Tool call insert identity matching [backend/database/repositories/users/tool_call_insert_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.database.requests import CreateToolCallResult
from core.errors.exceptions import StateError, ValidationError
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.tool_call_row_mapping import format_tool_call_row
from database.repositories.users.tool_call_validation import (
    parse_optional_json_from_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ValidatedToolCallInsertFields",
    "load_inserted_tool_call_result",
    "load_tool_call_by_storage_id",
    "validate_loaded_tool_call_matches_insert",
    "validate_loaded_tool_call_matches_insert_allowing_unknown_arguments",
)


@dataclass(frozen=True, slots=True)
class ValidatedToolCallInsertFields:
    storage_call_id: str
    conv_id: str
    assistant_turn_at_ms: int
    model_variant_index: int
    turn_id: str | None
    iteration_index: int | None
    message_index: int | None
    assistant_at_ms: int | None
    call_id: str
    tool_name: str
    tool_arguments: str | None
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None


def load_inserted_tool_call_result(
    conn: sqlite3.Connection,
    fields: ValidatedToolCallInsertFields,
) -> CreateToolCallResult:
    formatted = load_tool_call_by_storage_id(conn, fields.storage_call_id)
    validate_loaded_tool_call_matches_insert(formatted, fields)
    return CreateToolCallResult(row=formatted, inserted=True, claimed_existing=False)


def load_tool_call_by_storage_id(conn: sqlite3.Connection, storage_call_id: str) -> JSONDict:
    cursor = conn.execute("SELECT * FROM webui_chat_tool_calls WHERE id = ?", (storage_call_id,))
    formatted = format_tool_call_row(sync_fetch_one_as_dict(cursor))
    if formatted is None:
        raise StateError("Tool call exists but could not be loaded.")
    return formatted


def validate_loaded_tool_call_matches_insert(
    formatted: JSONDict,
    fields: ValidatedToolCallInsertFields,
) -> None:
    _validate_loaded_tool_call_identity_matches_insert(formatted, fields)
    stored_arguments = formatted.get("arguments")
    incoming_arguments = parse_optional_json_from_row(fields.tool_arguments, "tool_arguments")
    if stored_arguments != incoming_arguments:
        raise ValidationError("Tool call arguments do not match existing tool call record.")


def validate_loaded_tool_call_matches_insert_allowing_unknown_arguments(
    formatted: JSONDict,
    fields: ValidatedToolCallInsertFields,
) -> None:
    _validate_loaded_tool_call_identity_matches_insert(formatted, fields)
    stored_arguments = formatted.get("arguments")
    incoming_arguments = parse_optional_json_from_row(fields.tool_arguments, "tool_arguments")
    if (
        stored_arguments is not None
        and incoming_arguments is not None
        and stored_arguments != incoming_arguments
    ):
        raise ValidationError("Tool call arguments do not match existing tool call record.")


def _validate_loaded_tool_call_identity_matches_insert(
    formatted: JSONDict,
    fields: ValidatedToolCallInsertFields,
) -> None:
    if formatted.get("id") != fields.storage_call_id:
        raise ValidationError("Tool call id does not match existing tool call record.")
    if formatted.get("call_id") != fields.call_id:
        raise ValidationError("Tool call call_id does not match existing tool call record.")
    if formatted.get("conv_id") != fields.conv_id:
        raise ValidationError("Tool call conv_id does not match existing tool call record.")
    if formatted.get("message_index") != fields.message_index:
        raise ValidationError("Tool call message_index does not match existing tool call record.")
    if formatted.get("assistant_at_ms") != fields.assistant_at_ms:
        raise ValidationError("Tool call assistant_at_ms does not match existing tool call record.")
    if formatted.get("assistant_turn_at_ms") != fields.assistant_turn_at_ms:
        raise ValidationError(
            "Tool call assistant_turn_at_ms does not match existing tool call record.",
        )
    if formatted.get("model_variant_index") != fields.model_variant_index:
        raise ValidationError(
            "Tool call model_variant_index does not match existing tool call record.",
        )
    if formatted.get("turn_id") != fields.turn_id:
        raise ValidationError("Tool call turn_id does not match existing tool call record.")
    if formatted.get("iteration_index") != fields.iteration_index:
        raise ValidationError("Tool call iteration_index does not match existing tool call record.")
    if formatted.get("sequence_index") != fields.sequence_index:
        raise ValidationError("Tool call sequence_index does not match existing tool call record.")
    if formatted.get("tool_name") != fields.tool_name:
        raise ValidationError("Tool call tool_name does not match existing tool call record.")
    if formatted.get("content_index_before") != fields.content_index_before:
        raise ValidationError(
            "Tool call content_index_before does not match existing tool call record.",
        )
    if formatted.get("thinking_index_before") != fields.thinking_index_before:
        raise ValidationError(
            "Tool call thinking_index_before does not match existing tool call record.",
        )
    if formatted.get("thinking_duration_before_ms") != fields.thinking_duration_before_ms:
        raise ValidationError(
            "Tool call thinking_duration_before_ms does not match existing tool call record.",
        )

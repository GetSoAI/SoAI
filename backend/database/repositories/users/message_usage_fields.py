"""SoAI - Message usage row field decoding [backend/database/repositories/users/message_usage_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.assistant_usage_identity import (
    validate_assistant_usage_identity,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from database.core.row_fields import require_row_non_empty_str

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow, SQLiteValue

__all__ = ("MessageUsageFields", "read_message_usage_fields")


@dataclass(frozen=True, slots=True)
class MessageUsageFields:
    payload: JSONDict
    completion_tokens: int | None


def _read_optional_token(value: SQLiteValue, *, label: str) -> int | None:
    if value is None:
        return None
    if not is_strict_int(value):
        raise ValidationError(f"Conversation message {label} must be an integer.")
    return value


def read_message_usage_fields(row: SQLiteRow, *, role: str) -> MessageUsageFields:
    payload: JSONDict = {}
    request_id: str | None = None
    request_id_value = row.get("request_id")
    if request_id_value is not None:
        if role != "assistant":
            raise ValidationError("Conversation message request_id is only valid for assistants.")
        request_id = require_row_non_empty_str(
            request_id_value,
            label="Conversation message request_id",
            build_error=ValidationError,
        )
        payload["request_id"] = request_id

    prompt_tokens = _read_optional_token(row.get("prompt_tokens"), label="prompt_tokens")
    if prompt_tokens is not None:
        payload["prompt_tokens"] = prompt_tokens

    completion_tokens = _read_optional_token(
        row.get("completion_tokens"),
        label="completion_tokens",
    )
    if completion_tokens is not None:
        payload["completion_tokens"] = completion_tokens

    total_tokens = _read_optional_token(row.get("total_tokens"), label="total_tokens")
    if total_tokens is not None:
        payload["total_tokens"] = total_tokens

    usage_source: str | None = None
    usage_source_value = row.get("usage_source")
    if usage_source_value is not None:
        if role != "assistant":
            raise ValidationError("Conversation message usage_source is only valid for assistants.")
        usage_source = require_row_non_empty_str(
            usage_source_value,
            label="Conversation message usage_source",
            build_error=ValidationError,
        )
        payload["usage_source"] = usage_source

    validate_assistant_usage_identity(
        context_label="Conversation message",
        request_id=request_id,
        role=role,
        usage_source=usage_source,
        completion_tokens=completion_tokens,
        prompt_tokens=prompt_tokens,
        total_tokens=total_tokens,
    )
    return MessageUsageFields(payload=payload, completion_tokens=completion_tokens)

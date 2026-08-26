"""SoAI - Conversation message storage row construction [backend/database/repositories/users/message_storage_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.conversation_message_storage_types import (
    ConversationMessageStoragePayload,
)
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from database.core.sqlite_values import SQLiteValue
from database.repositories.users.message_content_integrity import (
    build_message_content_integrity,
)

__all__ = (
    "MESSAGE_INSERT_SQL",
    "MessageStorageRows",
    "build_message_storage_rows",
)

MESSAGE_INSERT_SQL = (
    "INSERT INTO webui_messages (conv_id, role, message_type, content, content_length, content_sha256, "
    "finalized_at_ms, created_at_ms, assistant_turn_at_ms, model_variant_index, request_id, "
    "model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, "
    "generation_latency_ms, finish_reason, thinking_tail_duration_ms) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

if TYPE_CHECKING:
    type MessageStorageRow = tuple[
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
        SQLiteValue,
    ]


@dataclass(frozen=True, slots=True)
class MessageStorageRows:
    rows: list[MessageStorageRow]
    deferred_assistant_finalization_timestamps: list[int]


def _requires_deferred_assistant_finalization(
    validated: ConversationMessageStoragePayload,
) -> bool:
    if validated.get("role") != "assistant":
        return False
    timeline = validated.get("assistant_event_timeline")
    return isinstance(timeline, list) and bool(timeline)


def _resolve_finalized_at_ms(
    *,
    validated: ConversationMessageStoragePayload,
    finalized_at_ms: int,
    defer_assistant_event_timeline_finalization: bool,
) -> int | None:
    if defer_assistant_event_timeline_finalization and _requires_deferred_assistant_finalization(
        validated,
    ):
        return None
    return finalized_at_ms


def build_message_storage_rows(
    *,
    conv_id: str,
    validated_messages: list[ConversationMessageStoragePayload],
    finalized_at_ms: int,
    defer_assistant_event_timeline_finalization: bool,
) -> MessageStorageRows:
    rows: list[MessageStorageRow] = []
    deferred_timestamps: list[int] = []
    for validated in validated_messages:
        content_json = validated["content_json"]
        if not isinstance(content_json, str):
            raise ValidationError("Validated message content must be a string.")
        created_at_ms = validated["created_at_ms"]
        if not is_strict_int(created_at_ms):
            raise ValidationError("Validated message created_at_ms must be an integer.")
        content_length, content_sha256 = build_message_content_integrity(content_json)
        row_finalized_at_ms = _resolve_finalized_at_ms(
            validated=validated,
            finalized_at_ms=finalized_at_ms,
            defer_assistant_event_timeline_finalization=(
                defer_assistant_event_timeline_finalization
            ),
        )
        if row_finalized_at_ms is None:
            deferred_timestamps.append(created_at_ms)
        rows.append(
            (
                conv_id,
                validated["role"],
                validated["message_type"],
                content_json,
                content_length,
                content_sha256,
                row_finalized_at_ms,
                created_at_ms,
                validated.get("assistant_turn_at_ms"),
                validated.get("model_variant_index"),
                validated.get("request_id"),
                validated.get("model_id"),
                validated.get("prompt_tokens"),
                validated.get("completion_tokens"),
                validated.get("total_tokens"),
                validated.get("usage_source"),
                validated.get("generation_latency_ms"),
                validated.get("finish_reason"),
                validated.get("thinking_tail_duration_ms"),
            ),
        )
    return MessageStorageRows(
        rows=rows,
        deferred_assistant_finalization_timestamps=deferred_timestamps,
    )

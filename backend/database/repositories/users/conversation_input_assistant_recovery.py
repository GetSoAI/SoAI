"""SoAI - Abandoned conversation input assistant recovery [backend/database/repositories/users/conversation_input_assistant_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.validation.integers import is_non_negative_strict_int, is_strict_int
from database.repositories.users.message_streaming_assistant.message_finalization_transactions import (
    sync_finalize_streaming_assistant_message,
)

__all__ = (
    "RecoveredConversationInputAssistant",
    "sync_finalize_abandoned_conversation_input_assistants",
)


@dataclass(frozen=True, slots=True)
class RecoveredConversationInputAssistant:
    message_id: int
    request_id: str
    finalized_at_ms: int | None
    finish_reason: str | None
    model_variant_index: int


def sync_finalize_abandoned_conversation_input_assistants(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    request_id: str,
    finish_reason: str,
    terminal_reason: str,
) -> tuple[tuple[RecoveredConversationInputAssistant, ...], int | None]:
    rows = sqlite_conn.execute(
        """
        SELECT id, created_at_ms, request_id, finalized_at_ms, finish_reason,
               model_variant_index, prompt_tokens, completion_tokens, total_tokens,
               usage_source, generation_latency_ms, thinking_tail_duration_ms
        FROM webui_messages
        WHERE conv_id = ? AND role = 'assistant'
          AND (request_id = ? OR request_id GLOB ?)
        ORDER BY model_variant_index ASC, id ASC
        """,
        (conv_id, request_id, f"{request_id}:variant:[0-9]*"),
    ).fetchall()
    assistants: list[RecoveredConversationInputAssistant] = []
    finalized_source_message_id: int | None = None
    for row in rows:
        message_id, created_at_ms, stored_request_id = row[0], row[1], row[2]
        finalized_at_ms, stored_finish_reason, model_variant_index = row[3], row[4], row[5]
        identity_valid = (
            is_strict_int(message_id)
            and is_strict_int(created_at_ms)
            and isinstance(stored_request_id, str)
            and bool(stored_request_id)
        )
        terminal_state_valid = (
            (finalized_at_ms is None or is_strict_int(finalized_at_ms))
            and (stored_finish_reason is None or isinstance(stored_finish_reason, str))
            and is_non_negative_strict_int(model_variant_index)
        )
        if not identity_valid or not terminal_state_valid:
            raise StateError("Recovered conversation input assistant identity is invalid.")
        assistants.append(
            RecoveredConversationInputAssistant(
                message_id=int(message_id),
                request_id=stored_request_id,
                finalized_at_ms=(int(finalized_at_ms) if finalized_at_ms is not None else None),
                finish_reason=stored_finish_reason,
                model_variant_index=int(model_variant_index),
            ),
        )
        if finalized_at_ms is not None:
            continue
        sync_finalize_streaming_assistant_message(
            sqlite_conn,
            conv_id,
            user_id,
            int(created_at_ms),
            stored_request_id,
            finish_reason,
            row[6],
            row[7],
            row[8],
            row[9],
            row[10],
            row[11],
            terminal_reason,
        )
        finalized_source_message_id = int(message_id)
    return tuple(assistants), finalized_source_message_id

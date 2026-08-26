"""SoAI - Streaming assistant finalization transactions [backend/database/repositories/users/message_streaming_assistant/message_finalization_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.conversations.assistant_usage_identity import (
    validate_assistant_usage_identity,
)
from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.conversations.streaming_message_errors import (
    StreamingAssistantMessageAlreadyFinalizedError,
)
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.validation.record_fields import require_optional_non_empty_str
from database.repositories.users.conversation_attention import (
    sync_replace_conversation_attention,
)
from database.repositories.users.conversation_input_terminalization import (
    sync_terminalize_conversation_input,
)
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
)
from database.repositories.users.message_content_integrity import (
    build_message_content_integrity,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages
from database.repositories.users.message_streaming_assistant.terminal_event_normalization import (
    sync_normalize_terminal_assistant_events,
)

if TYPE_CHECKING:
    from core.conversations.conversation_input_finalization import (
        ConversationInputFinalization,
    )

__all__ = ("sync_finalize_streaming_assistant_message",)


def _raise_missing_or_finalized(
    conn: sqlite3.Connection,
    conv_id: str,
    created_at_ms: int,
) -> None:
    finalized_row = conn.execute(
        (
            "SELECT finalized_at_ms FROM webui_messages "
            "WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant'"
        ),
        (conv_id, created_at_ms),
    ).fetchone()
    if finalized_row is not None and finalized_row[0] is not None:
        raise StreamingAssistantMessageAlreadyFinalizedError(
            "Streaming assistant message is already finalized."
        )
    raise ValidationError("Streaming assistant message not found.")


def sync_finalize_streaming_assistant_message(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    created_at_ms: int,
    request_id: str | None,
    finish_reason: str | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    total_tokens: int | None,
    usage_source: str | None,
    generation_latency_ms: int | None,
    thinking_tail_duration_ms: int | None,
    terminal_reason: str | None,
    input_finalization: ConversationInputFinalization | None = None,
    input_terminal_code: str | None = None,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    content_row = conn.execute(
        (
            "SELECT id, content, finalized_at_ms FROM webui_messages "
            "WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant'"
        ),
        (conv_id, created_at_ms),
    ).fetchone()
    if content_row is None:
        raise ValidationError("Streaming assistant message not found.")
    if content_row[2] is not None:
        raise StreamingAssistantMessageAlreadyFinalizedError(
            "Streaming assistant message is already finalized."
        )
    assistant_message_id = content_row[0]
    if not isinstance(assistant_message_id, int):
        raise ValidationError("Streaming assistant message id is invalid.")
    content_value = content_row[1]
    if not isinstance(content_value, str):
        raise ValidationError("Streaming assistant message content must be stored as text.")
    content_length, content_sha256 = build_message_content_integrity(content_value)
    finalized_at = epoch_ms()
    normalized_request_id = require_optional_non_empty_str(
        request_id,
        label="Streaming assistant request_id",
        build_error=ValidationError,
        invalid_message="Streaming assistant request_id must be non-empty when provided.",
    )
    normalized_usage_source = require_optional_non_empty_str(
        usage_source,
        label="Streaming assistant usage_source",
        build_error=ValidationError,
        invalid_message="Streaming assistant usage_source must be non-empty when provided.",
    )
    validate_assistant_usage_identity(
        role="assistant",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        request_id=normalized_request_id,
        usage_source=normalized_usage_source,
        context_label="Streaming assistant",
    )
    sync_normalize_terminal_assistant_events(
        conn,
        conv_id=conv_id,
        assistant_at_ms=created_at_ms,
        finish_reason=finish_reason,
        terminal_reason=terminal_reason,
    )
    cursor = conn.execute(
        (
            "UPDATE webui_messages SET content_length = ?, content_sha256 = ?, "
            "finalized_at_ms = ?, request_id = COALESCE(?, request_id), finish_reason = ?, "
            "prompt_tokens = ?, completion_tokens = ?, total_tokens = ?, usage_source = ?, "
            "generation_latency_ms = ?, thinking_tail_duration_ms = ? "
            "WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant' "
            "AND finalized_at_ms IS NULL"
        ),
        (
            content_length,
            content_sha256,
            finalized_at,
            normalized_request_id,
            finish_reason,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            normalized_usage_source,
            generation_latency_ms,
            thinking_tail_duration_ms,
            conv_id,
            created_at_ms,
        ),
    )
    if cursor.rowcount <= 0:
        _raise_missing_or_finalized(conn, conv_id, created_at_ms)
    if input_finalization is not None:
        _terminalize_input_with_assistant(
            conn,
            conv_id=conv_id,
            created_at_ms=created_at_ms,
            finish_reason=finish_reason,
            terminal_code=input_terminal_code,
            input_finalization=input_finalization,
        )
    sync_replace_conversation_attention(
        conn,
        user_id=user_id,
        conv_id=conv_id,
        assistant_message_id=assistant_message_id,
        finish_reason=finish_reason,
        created_at_ms=finalized_at,
    )
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
    )


def _terminalize_input_with_assistant(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    created_at_ms: int,
    finish_reason: str | None,
    terminal_code: str | None,
    input_finalization: ConversationInputFinalization,
) -> None:
    if finish_reason not in {"error", "cancelled"} and not input_finalization.final_planned_variant:
        return
    message_row = conn.execute(
        (
            "SELECT id FROM webui_messages WHERE conv_id = ? "
            "AND created_at_ms = ? AND role = 'assistant'"
        ),
        (conv_id, created_at_ms),
    ).fetchone()
    if message_row is None or not isinstance(message_row[0], int):
        raise ValidationError("Finalized assistant message identity is unavailable.")
    if finish_reason == "cancelled":
        terminal_state = "cancelled"
    elif finish_reason == "error":
        terminal_state = "failed"
    else:
        terminal_state = "completed"
    normalized_code = terminal_code.strip() if isinstance(terminal_code, str) else ""
    if not normalized_code:
        raise ValidationError("Conversation input terminal code is unavailable.")
    sync_terminalize_conversation_input(
        conn,
        input_finalization.input_id,
        input_finalization.claim_generation,
        input_finalization.claim_owner,
        input_finalization.server_boot_id,
        terminal_state,
        normalized_code,
        {},
        message_row[0],
    )

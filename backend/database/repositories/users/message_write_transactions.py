"""SoAI - Message repository write transactions [backend/database/repositories/users/message_write_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.conversations.conversation_message_storage_validation import (
    validate_messages_payload_for_storage,
)
from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.repositories.users.conversation_attachment_message_sync import (
    sync_apply_append_attachment_references,
    sync_apply_overwrite_attachment_references,
)
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_soai_path_reference_validation import (
    sync_canonicalize_soai_path_references,
)
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
    sync_load_conversation_last_modified_at_ms,
    sync_require_expected_conversation_version,
)
from database.repositories.users.message_append_order_validation import (
    sync_require_append_timestamps_after_existing,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages
from database.repositories.users.message_overwrite_reconciliation import (
    sync_reconcile_overwritten_message_auxiliary_tables,
)
from database.repositories.users.message_storage_rows import (
    MESSAGE_INSERT_SQL,
    build_message_storage_rows,
)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import FilesProtocol

__all__ = (
    "sync_append_messages",
    "sync_overwrite_messages",
)


def sync_overwrite_messages(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    messages: list[JSONDict],
    expected_last_modified_at_ms: int | None = None,
    storage_root: str | None = None,
    files: FilesProtocol | None = None,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    sync_require_expected_conversation_version(
        conn,
        conv_id=conv_id,
        expected_last_modified_at_ms=expected_last_modified_at_ms,
    )
    existing_count = sync_count_stored_messages(conn, conv_id)
    now = epoch_ms()
    canonical_messages = sync_canonicalize_soai_path_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        messages=messages,
        files=files,
        resolved_at_ms=now,
    )
    (
        canonical_messages,
        knowledge_attachment_summaries,
    ) = sync_apply_overwrite_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        messages=canonical_messages,
        updated_at_ms=now,
        storage_root=storage_root,
    )
    validated_messages = validate_messages_payload_for_storage(canonical_messages)
    storage_rows = build_message_storage_rows(
        conv_id=conv_id,
        validated_messages=validated_messages,
        finalized_at_ms=now,
        defer_assistant_event_timeline_finalization=True,
    )
    if existing_count:
        conn.execute("DELETE FROM webui_messages WHERE conv_id = ?", (conv_id,))
    if storage_rows.rows:
        conn.executemany(MESSAGE_INSERT_SQL, storage_rows.rows)
    sync_reconcile_overwritten_message_auxiliary_tables(
        conn,
        conv_id=conv_id,
        validated_messages=validated_messages,
        finalized_at_ms=now,
        assistant_timestamps_to_finalize=(storage_rows.deferred_assistant_finalization_timestamps),
    )
    if existing_count or validated_messages:
        last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    else:
        last_modified_at_ms = sync_load_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
        canonical_messages=canonical_messages,
        knowledge_attachment_summaries=knowledge_attachment_summaries,
    )


def sync_append_messages(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    messages: list[JSONDict],
    expected_last_modified_at_ms: int | None = None,
    storage_root: str | None = None,
    files: FilesProtocol | None = None,
    conversation_input_id: str | None = None,
    soai_path_resolved_at_ms: int | None = None,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    sync_require_expected_conversation_version(
        conn,
        conv_id=conv_id,
        expected_last_modified_at_ms=expected_last_modified_at_ms,
    )
    now = epoch_ms()
    resolved_at_ms = now if soai_path_resolved_at_ms is None else soai_path_resolved_at_ms
    canonical_messages = sync_canonicalize_soai_path_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        messages=messages,
        files=files,
        resolved_at_ms=resolved_at_ms,
    )
    (
        canonical_messages,
        knowledge_attachment_summaries,
    ) = sync_apply_append_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        messages=canonical_messages,
        updated_at_ms=now,
        conversation_input_id=conversation_input_id,
        storage_root=storage_root,
    )
    validated_messages = validate_messages_payload_for_storage(canonical_messages)
    sync_require_append_timestamps_after_existing(
        conn,
        conv_id=conv_id,
        validated_messages=validated_messages,
    )
    storage_rows = build_message_storage_rows(
        conv_id=conv_id,
        validated_messages=validated_messages,
        finalized_at_ms=now,
        defer_assistant_event_timeline_finalization=False,
    )
    if storage_rows.rows:
        conn.executemany(MESSAGE_INSERT_SQL, storage_rows.rows)
        last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    else:
        last_modified_at_ms = sync_load_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
        canonical_messages=canonical_messages,
        knowledge_attachment_summaries=knowledge_attachment_summaries,
    )

"""SoAI - Conversation draft write transactions [backend/database/repositories/users/conversation_draft_sync_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3
from typing import TYPE_CHECKING

from core.conversations.conversation_draft_content_validation import (
    CHAT_COMPOSER_TEXT_MAX_LENGTH,
    validate_conversation_draft_entries,
)
from core.conversations.conversation_draft_state import ConversationDraftMutationResult
from core.errors.exceptions import ConcurrencyError, ConflictError, StateError, ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_references import (
    extract_content_attachment_references,
)
from database.repositories.users.conversation_draft_attachment_content import (
    canonicalize_conversation_draft_attachment_content,
    require_non_empty_conversation_draft,
)
from database.repositories.users.conversation_draft_queries import (
    query_conversation_draft_state,
)
from database.repositories.users.conversation_draft_row_mapping import (
    serialize_conversation_draft_entries,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_delete_conversation_draft", "sync_save_conversation_draft")


def _mutation_signature(
    *,
    deleted: bool,
    text: str,
    source_text: str,
    attachment_content_json: str,
    base_revision: int,
) -> str:
    serialized = serialize_json_compact_stable(
        {
            "deleted": deleted,
            "text": text,
            "source_text": source_text,
            "attachment_content_json": attachment_content_json,
            "base_revision": base_revision,
        },
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _fetch_current_row(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> SQLiteRowDict | None:
    return sync_fetch_one_as_dict(
        sqlite_conn.execute(
            """
            SELECT revision
            FROM webui_conversation_drafts
            WHERE conv_id = ? AND user_id = ?
            """,
            (conv_id, user_id),
        ),
    )


def _require_current_revision(row: SQLiteRowDict | None) -> int:
    if row is None:
        return 0
    revision = row.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise StateError("Conversation draft revision is invalid.")
    return revision


def _resolve_idempotent_replay(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    client_id: str,
    client_sequence: int,
    mutation_signature: str,
) -> bool:
    row = sync_fetch_one_as_dict(
        sqlite_conn.execute(
            """
            SELECT payload_signature
            FROM webui_conversation_draft_mutations
            WHERE conv_id = ? AND user_id = ? AND client_id = ? AND client_sequence = ?
            """,
            (conv_id, user_id, client_id, client_sequence),
        ),
    )
    if row is None:
        return False
    if row.get("payload_signature") != mutation_signature:
        raise ConflictError("Conversation draft mutation identity was reused.")
    return True


def _require_base_revision(base_revision: int, current_revision: int) -> None:
    if base_revision == current_revision:
        return
    raise ConcurrencyError(
        "Conversation draft revision conflict.",
        details={"authoritative_revision": current_revision},
    )


def _upsert_draft_row(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    text: str,
    source_text: str,
    attachment_content_json: str,
    deleted: bool,
    updated_at_ms: int,
    client_id: str,
    client_sequence: int,
    revision: int,
    mutation_signature: str,
) -> None:
    sqlite_conn.execute(
        """
        INSERT INTO webui_conversation_drafts (
            conv_id, user_id, text, source_text, attachment_content_json, is_deleted,
            created_at_ms, updated_at_ms, client_id, client_sequence, revision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(conv_id, user_id) DO UPDATE SET
            text = excluded.text,
            source_text = excluded.source_text,
            attachment_content_json = excluded.attachment_content_json,
            is_deleted = excluded.is_deleted,
            updated_at_ms = excluded.updated_at_ms,
            client_id = excluded.client_id,
            client_sequence = excluded.client_sequence,
            revision = excluded.revision
        """,
        (
            conv_id,
            user_id,
            text,
            source_text,
            attachment_content_json,
            int(deleted),
            updated_at_ms,
            updated_at_ms,
            client_id,
            client_sequence,
            revision,
        ),
    )
    sqlite_conn.execute(
        """
        INSERT INTO webui_conversation_draft_mutations (
            conv_id, user_id, client_id, client_sequence, payload_signature, result_revision
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            conv_id,
            user_id,
            client_id,
            client_sequence,
            mutation_signature,
            revision,
        ),
    )


def sync_save_conversation_draft(
    sqlite_conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    text: str,
    source_text: str,
    attachment_content_json: str,
    client_id: str,
    client_sequence: int,
    base_revision: int,
    updated_at_ms: int,
    storage_root: str | None = None,
) -> ConversationDraftMutationResult:
    parsed_json = parse_json_value(
        attachment_content_json,
        field="conversation draft attachment_content_json",
    )
    if not isinstance(parsed_json, list):
        raise ValidationError("Conversation draft attachment_content_json must be a JSON array.")
    parsed_entries = validate_conversation_draft_entries(parsed_json)
    require_non_empty_conversation_draft(text, parsed_entries)
    if (
        len(text) > CHAT_COMPOSER_TEXT_MAX_LENGTH
        or len(source_text) > CHAT_COMPOSER_TEXT_MAX_LENGTH
    ):
        raise ValidationError("Conversation draft text exceeds the maximum length.")
    request_json = serialize_conversation_draft_entries(parsed_entries)
    mutation_signature = _mutation_signature(
        deleted=False,
        text=text,
        source_text=source_text,
        attachment_content_json=request_json,
        base_revision=base_revision,
    )
    current_row = _fetch_current_row(sqlite_conn, conv_id=conv_id, user_id=user_id)
    if _resolve_idempotent_replay(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        client_id=client_id,
        client_sequence=client_sequence,
        mutation_signature=mutation_signature,
    ):
        return ConversationDraftMutationResult(
            state=query_conversation_draft_state(sqlite_conn, conv_id, user_id),
            applied=False,
        )
    current_revision = _require_current_revision(current_row)
    _require_base_revision(base_revision, current_revision)
    references = extract_content_attachment_references(
        parsed_entries,
        message_created_at_ms=updated_at_ms,
    )
    canonical_entries = canonicalize_conversation_draft_attachment_content(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        entries=parsed_entries,
        references=references,
        storage_root=storage_root,
    )
    _upsert_draft_row(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        text=text,
        source_text=source_text,
        attachment_content_json=serialize_conversation_draft_entries(canonical_entries),
        deleted=False,
        updated_at_ms=updated_at_ms,
        client_id=client_id,
        client_sequence=client_sequence,
        revision=current_revision + 1,
        mutation_signature=mutation_signature,
    )
    return ConversationDraftMutationResult(
        state=query_conversation_draft_state(sqlite_conn, conv_id, user_id),
        applied=True,
    )


def sync_delete_conversation_draft(
    sqlite_conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    client_id: str,
    client_sequence: int,
    base_revision: int,
    updated_at_ms: int,
) -> ConversationDraftMutationResult:
    mutation_signature = _mutation_signature(
        deleted=True,
        text="",
        source_text="",
        attachment_content_json="[]",
        base_revision=base_revision,
    )
    current_row = _fetch_current_row(sqlite_conn, conv_id=conv_id, user_id=user_id)
    if _resolve_idempotent_replay(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        client_id=client_id,
        client_sequence=client_sequence,
        mutation_signature=mutation_signature,
    ):
        return ConversationDraftMutationResult(
            state=query_conversation_draft_state(sqlite_conn, conv_id, user_id),
            applied=False,
        )
    current_revision = _require_current_revision(current_row)
    _require_base_revision(base_revision, current_revision)
    _upsert_draft_row(
        sqlite_conn,
        conv_id=conv_id,
        user_id=user_id,
        text="",
        source_text="",
        attachment_content_json="[]",
        deleted=True,
        updated_at_ms=updated_at_ms,
        client_id=client_id,
        client_sequence=client_sequence,
        revision=current_revision + 1,
        mutation_signature=mutation_signature,
    )
    return ConversationDraftMutationResult(
        state=query_conversation_draft_state(sqlite_conn, conv_id, user_id),
        applied=True,
    )

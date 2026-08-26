"""SoAI - RAG Knowledge prompt serialized writes [backend/database/repositories/rag_knowledge_prompt_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import Literal

from core.rag.knowledge_prompt_types import (
    KnowledgePromptClaimResult,
    KnowledgePromptEventRecord,
)
from core.types.json import JSONDict
from database.core.json_codec import safe_json_serialize_value
from database.repositories.rag_knowledge_prompt_records import (
    parse_knowledge_prompt_event_record,
)

__all__ = (
    "sync_clear_expired_claim",
    "sync_commit_active_claim",
    "sync_create_or_reuse_delivery_claim",
    "sync_record_knowledge_event",
    "sync_release_active_claim",
)

_MAX_DOCUMENT_NAME_SAMPLE = 20


def sync_record_knowledge_event(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    event_type: Literal[
        "documents_added",
        "documents_removed",
        "document_processing_completed",
        "document_processing_failed",
        "document_processing_cancelled",
        "knowledge_reindex_queued",
        "knowledge_reindex_completed",
        "knowledge_reindex_failed",
        "knowledge_reindex_cancelled",
    ],
    document_names: list[str],
    document_count: int,
    details: JSONDict,
    created_at_ms: int,
) -> KnowledgePromptEventRecord:
    cursor = conn.execute(
        """INSERT INTO rag_knowledge_prompt_events (
            conv_id, user_id, event_type, document_names_json, document_count,
            details_json, created_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            conv_id,
            user_id,
            event_type,
            safe_json_serialize_value(
                document_names[:_MAX_DOCUMENT_NAME_SAMPLE],
                field_name="document_names_json",
                identifier=conv_id,
            ),
            int(document_count),
            safe_json_serialize_value(details, field_name="details_json", identifier=conv_id),
            created_at_ms,
        ),
    )
    event_id = int(cursor.lastrowid or 0)
    row = conn.execute(
        """SELECT id, conv_id, user_id, event_type, document_names_json, document_count,
                  details_json, created_at_ms
           FROM rag_knowledge_prompt_events
           WHERE id = ?""",
        (event_id,),
    ).fetchone()
    if row is None:
        raise sqlite3.DatabaseError("Failed to read inserted Knowledge prompt event.")
    return parse_knowledge_prompt_event_record(dict(row))


def sync_clear_expired_claim(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    now_ms: int,
) -> bool:
    before = conn.total_changes
    conn.execute(
        """UPDATE rag_knowledge_prompt_delivery
           SET active_claim_id = NULL,
               active_claim_request_id = NULL,
               active_claim_event_ceiling_id = NULL,
               active_claim_state_signature = NULL,
               active_claim_expires_at_ms = NULL
           WHERE conv_id = ? AND user_id = ? AND active_claim_expires_at_ms <= ?""",
        (conv_id, user_id, int(now_ms)),
    )
    return conn.total_changes > before


def sync_create_or_reuse_delivery_claim(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    request_id: str,
    claim_id: str,
    event_ceiling_id: int,
    state_signature: str,
    expires_at_ms: int,
    now_ms: int,
) -> KnowledgePromptClaimResult:
    conn.execute(
        """INSERT OR IGNORE INTO rag_knowledge_prompt_delivery (conv_id, user_id)
           VALUES (?, ?)""",
        (conv_id, user_id),
    )
    row = conn.execute(
        """SELECT active_claim_id, active_claim_request_id, active_claim_event_ceiling_id,
                  active_claim_state_signature, active_claim_expires_at_ms
           FROM rag_knowledge_prompt_delivery
           WHERE conv_id = ? AND user_id = ?""",
        (conv_id, user_id),
    ).fetchone()
    active_claim_id = row["active_claim_id"] if row is not None else None
    active_request_id = row["active_claim_request_id"] if row is not None else None
    active_event_ceiling_id = row["active_claim_event_ceiling_id"] if row is not None else None
    active_state_signature = row["active_claim_state_signature"] if row is not None else None
    active_expires = row["active_claim_expires_at_ms"] if row is not None else None
    if isinstance(active_expires, int) and active_expires <= now_ms:
        sync_clear_expired_claim(conn, conv_id, user_id, now_ms)
        active_claim_id = None
        active_request_id = None
    if active_claim_id and active_request_id == request_id:
        if not isinstance(active_event_ceiling_id, int) or not isinstance(
            active_state_signature,
            str,
        ):
            return KnowledgePromptClaimResult(False, None, None, None, None)
        return KnowledgePromptClaimResult(
            True,
            str(active_claim_id),
            request_id,
            active_event_ceiling_id,
            active_state_signature,
        )
    if active_claim_id:
        return KnowledgePromptClaimResult(False, None, None, None, None)
    conn.execute(
        """UPDATE rag_knowledge_prompt_delivery
           SET active_claim_id = ?,
               active_claim_request_id = ?,
               active_claim_event_ceiling_id = ?,
               active_claim_state_signature = ?,
               active_claim_expires_at_ms = ?
           WHERE conv_id = ? AND user_id = ?""",
        (
            claim_id,
            request_id,
            int(event_ceiling_id),
            state_signature,
            int(expires_at_ms),
            conv_id,
            user_id,
        ),
    )
    return KnowledgePromptClaimResult(True, claim_id, request_id, event_ceiling_id, state_signature)


def sync_commit_active_claim(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    claim_id: str,
    request_id: str,
    event_ceiling_id: int,
    state_signature: str,
    delivered_at_ms: int,
) -> bool:
    before = conn.total_changes
    conn.execute(
        """UPDATE rag_knowledge_prompt_delivery
           SET last_delivered_event_id = ?,
               last_delivered_state_signature = ?,
               active_claim_id = NULL,
               active_claim_request_id = NULL,
               active_claim_event_ceiling_id = NULL,
               active_claim_state_signature = NULL,
               active_claim_expires_at_ms = NULL,
               last_delivered_at_ms = ?
           WHERE conv_id = ?
             AND user_id = ?
             AND active_claim_id = ?
             AND active_claim_request_id = ?""",
        (
            int(event_ceiling_id),
            state_signature,
            int(delivered_at_ms),
            conv_id,
            user_id,
            claim_id,
            request_id,
        ),
    )
    return conn.total_changes > before


def sync_release_active_claim(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    claim_id: str,
    request_id: str,
) -> bool:
    before = conn.total_changes
    conn.execute(
        """UPDATE rag_knowledge_prompt_delivery
           SET active_claim_id = NULL,
               active_claim_request_id = NULL,
               active_claim_event_ceiling_id = NULL,
               active_claim_state_signature = NULL,
               active_claim_expires_at_ms = NULL
           WHERE conv_id = ?
             AND user_id = ?
             AND active_claim_id = ?
             AND active_claim_request_id = ?""",
        (conv_id, user_id, claim_id, request_id),
    )
    return conn.total_changes > before

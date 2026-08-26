"""SoAI - RAG conversation maintenance lock transactions [backend/database/repositories/files/rag_maintenance_locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.core.query_execution import sync_fetch_changes_count

__all__ = (
    "sync_acquire_rag_maintenance_lock",
    "sync_release_rag_maintenance_lock",
    "sync_renew_rag_maintenance_lock",
)


def sync_acquire_rag_maintenance_lock(
    conn: sqlite3.Connection,
    conv_id: str,
    lock_type: str,
    owner_task_id: str,
    lease_token: str,
    lease_owner: str,
    lease_expires_at_ms: int,
    now_ms: int,
) -> bool:
    conn.execute(
        "DELETE FROM rag_conversation_maintenance_locks WHERE lease_expires_at_ms < ?",
        (now_ms,),
    )
    conn.execute(
        """
        INSERT INTO rag_conversation_maintenance_locks (
            conv_id, lock_type, owner_task_id, lease_token, lease_owner,
            lease_expires_at_ms, created_at_ms, updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(conv_id) DO NOTHING
        """,
        (
            conv_id,
            lock_type,
            owner_task_id,
            lease_token,
            lease_owner,
            lease_expires_at_ms,
            now_ms,
            now_ms,
        ),
    )
    return sync_fetch_changes_count(conn) > 0


def sync_release_rag_maintenance_lock(
    conn: sqlite3.Connection,
    conv_id: str,
    lease_token: str,
) -> None:
    conn.execute(
        "DELETE FROM rag_conversation_maintenance_locks WHERE conv_id = ? AND lease_token = ?",
        (conv_id, lease_token),
    )


def sync_renew_rag_maintenance_lock(
    conn: sqlite3.Connection,
    conv_id: str,
    lease_token: str,
    lease_expires_at_ms: int,
    now_ms: int,
) -> bool:
    conn.execute(
        """
        UPDATE rag_conversation_maintenance_locks
        SET lease_expires_at_ms = ?, updated_at_ms = ?
        WHERE conv_id = ? AND lease_token = ?
        """,
        (lease_expires_at_ms, now_ms, conv_id, lease_token),
    )
    return sync_fetch_changes_count(conn) > 0

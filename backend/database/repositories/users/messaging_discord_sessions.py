"""SoAI - Durable Discord Gateway session transitions [backend/database/repositories/users/messaging_discord_sessions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import replace
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from core.errors.exceptions import ConflictError, StateError
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.messaging_ingress_admission import (
    sync_admit_messaging_event,
)

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = (
    "sync_begin_discord_connection",
    "sync_close_discord_session",
    "sync_commit_discord_dispatch",
    "sync_mark_discord_session_gap",
    "sync_record_discord_ready",
)


def _read_session(conn: sqlite3.Connection, account_id: str) -> JSONDict:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT * FROM messaging_discord_sessions WHERE account_id = ?",
            (account_id,),
        ),
    )
    if row is None:
        raise StateError("Discord session is unavailable.")
    return dict(row)


def sync_begin_discord_connection(
    conn: sqlite3.Connection,
    account_id: str,
    user_id: int,
    updated_at_ms: int,
) -> JSONDict:
    account = conn.execute(
        """
        SELECT lifecycle_state
        FROM messaging_accounts
        WHERE account_id = ? AND user_id = ? AND platform = 'discord'
        """,
        (account_id, user_id),
    ).fetchone()
    if account is None or account[0] not in ("enabled", "degraded"):
        raise ConflictError("Discord account admission is closed.")
    conn.execute(
        """
        INSERT INTO messaging_discord_sessions (
            account_id, user_id, connection_generation, session_state, updated_at_ms
        ) VALUES (?, ?, 1, 'new', ?)
        ON CONFLICT(account_id) DO UPDATE SET
            connection_generation = connection_generation + 1,
            session_state = CASE
                WHEN session_id IS NOT NULL AND session_state IN ('resumable', 'closed')
                    THEN 'resumable'
                ELSE 'new'
            END,
            updated_at_ms = excluded.updated_at_ms
        """,
        (account_id, user_id, updated_at_ms),
    )
    return _read_session(conn, account_id)


def sync_record_discord_ready(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    account_id: str,
    connection_generation: int,
    event: NormalizedMessagingEvent,
    session_id: str,
    resume_gateway_url: str,
    ingress_id: str,
    content_fingerprint: str,
    updated_at_ms: int,
) -> JSONDict:
    dispatch_sequence = event.discord_dispatch_sequence
    if dispatch_sequence is None:
        raise StateError("Discord READY Dispatch sequence is required.")
    updated = conn.execute(
        """
        UPDATE messaging_discord_sessions
        SET session_id = ?, resume_gateway_url = ?,
            committed_dispatch_sequence = ?, session_state = 'resumable', updated_at_ms = ?
        WHERE account_id = ? AND connection_generation = ?
        """,
        (
            session_id,
            resume_gateway_url,
            dispatch_sequence,
            updated_at_ms,
            account_id,
            connection_generation,
        ),
    ).rowcount
    if updated != 1:
        raise ConflictError("Discord connection generation changed before READY commit.")
    scoped_event = replace(
        event,
        provider_event_id=f"session:{session_id}:{event.provider_event_id}",
    )
    result = sync_admit_messaging_event(
        conn,
        fernets,
        account_id,
        ingress_id,
        "unused",
        "unused",
        scoped_event,
        content_fingerprint,
        "Discord session",
        updated_at_ms,
        None,
    )
    result["connection_generation"] = connection_generation
    result["committed_dispatch_sequence"] = dispatch_sequence
    return result


def _scope_discord_protocol_event(
    event: NormalizedMessagingEvent,
    session: JSONDict,
) -> NormalizedMessagingEvent:
    if event.provider_message_id is not None:
        return event
    session_id = session.get("session_id")
    if not isinstance(session_id, str):
        raise StateError("Discord session identity is unavailable.")
    return replace(
        event,
        provider_event_id=f"session:{session_id}:{event.provider_event_id}",
    )


def sync_commit_discord_dispatch(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    account_id: str,
    connection_generation: int,
    event: NormalizedMessagingEvent,
    ingress_id: str,
    input_id: str,
    conversation_id: str,
    content_fingerprint: str,
    title: str,
    accepted_at_ms: int,
    storage_root: str | None,
) -> JSONDict:
    sequence = event.discord_dispatch_sequence
    if sequence is None:
        raise StateError("Discord Dispatch sequence is required.")
    session = _read_session(conn, account_id)
    if session.get("connection_generation") != connection_generation:
        raise ConflictError("Discord connection generation changed.")
    committed = session.get("committed_dispatch_sequence")
    if isinstance(committed, int) and sequence < committed:
        raise ConflictError("Discord Dispatch sequence regressed.")
    if isinstance(committed, int) and sequence == committed:
        retained = conn.execute(
            """
            SELECT 1 FROM messaging_ingress_events
            WHERE account_id = ? AND discord_dispatch_sequence = ?
            LIMIT 1
            """,
            (account_id, sequence),
        ).fetchone()
        if retained is None:
            return {
                "status": "ignored",
                "outcome": "rejected",
                "diagnostic_code": "discord_dispatch_already_committed",
                "committed_dispatch_sequence": sequence,
            }
    if isinstance(committed, int) and sequence > committed + 1:
        raise ConflictError("Discord Dispatch sequence has a gap.")
    scoped_event = _scope_discord_protocol_event(event, session)
    result = sync_admit_messaging_event(
        conn,
        fernets,
        account_id,
        ingress_id,
        input_id,
        conversation_id,
        scoped_event,
        content_fingerprint,
        title,
        accepted_at_ms,
        storage_root,
    )
    updated = conn.execute(
        """
        UPDATE messaging_discord_sessions
        SET committed_dispatch_sequence = CASE
                WHEN committed_dispatch_sequence IS NULL OR committed_dispatch_sequence < ? THEN ?
                ELSE committed_dispatch_sequence
            END,
            session_state = 'resumable', updated_at_ms = ?
        WHERE account_id = ? AND connection_generation = ?
        """,
        (sequence, sequence, accepted_at_ms, account_id, connection_generation),
    ).rowcount
    if updated != 1:
        raise ConflictError("Discord connection generation changed before Dispatch commit.")
    result["committed_dispatch_sequence"] = sequence
    return result


def _set_discord_session_state(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    connection_generation: int,
    session_state: str,
    clear_resume: bool,
    updated_at_ms: int,
) -> None:
    updated = conn.execute(
        """
        UPDATE messaging_discord_sessions
        SET session_state = ?,
            session_id = CASE WHEN ? THEN NULL ELSE session_id END,
            resume_gateway_url = CASE WHEN ? THEN NULL ELSE resume_gateway_url END,
            committed_dispatch_sequence = CASE
                WHEN ? THEN NULL ELSE committed_dispatch_sequence
            END,
            updated_at_ms = ?
        WHERE account_id = ? AND connection_generation = ?
        """,
        (
            session_state,
            clear_resume,
            clear_resume,
            clear_resume,
            updated_at_ms,
            account_id,
            connection_generation,
        ),
    ).rowcount
    if updated not in (0, 1):
        raise StateError("Discord session transition affected multiple rows.")


def sync_mark_discord_session_gap(
    conn: sqlite3.Connection,
    account_id: str,
    connection_generation: int,
    updated_at_ms: int,
) -> None:
    _set_discord_session_state(
        conn,
        account_id=account_id,
        connection_generation=connection_generation,
        session_state="gap",
        clear_resume=True,
        updated_at_ms=updated_at_ms,
    )


def sync_close_discord_session(
    conn: sqlite3.Connection,
    account_id: str,
    connection_generation: int,
    updated_at_ms: int,
) -> None:
    _set_discord_session_state(
        conn,
        account_id=account_id,
        connection_generation=connection_generation,
        session_state="closed",
        clear_resume=False,
        updated_at_ms=updated_at_ms,
    )

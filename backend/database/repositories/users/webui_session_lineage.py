"""SoAI - Transactional WebUI session lineage recovery and revocation [backend/database/repositories/users/webui_session_lineage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import time

from core.auth.protocols_database_tokens import (
    SessionLineageRevocationResult,
    SessionRotationRecoveryState,
)
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from database.repositories.users.user_event_outbox import sync_enqueue_user_domain_event
from database.repositories.users.user_row_normalization import normalize_user_row
from database.repositories.users.webui_session_lineage_validation import (
    sync_resolve_terminal_session_jti,
)
from database.repositories.users.webui_session_writes import (
    sync_revoke_active_user_sessions,
)


def sync_recover_session_rotation(
    conn: sqlite3.Connection,
    source_jti: str,
    user_id: int,
    source_password_revision: int,
    source_issued_at_ms: int,
    source_expires_at_ms: int,
    observed_at_ms: int,
) -> SessionRotationRecoveryState:
    row = conn.execute(
        """
        SELECT users.*, rotations.replacement_jti,
               rotations.replacement_issued_at_ms,
               rotations.replacement_expires_at_ms,
               rotations.replacement_password_revision,
               rotations.operation_id
        FROM webui_session_rotations rotations
        JOIN webui_users users ON users.id = rotations.user_id
        JOIN webui_device_sessions source
          ON source.jti = rotations.source_jti
         AND source.user_id = rotations.user_id
        JOIN webui_device_sessions replacement
          ON replacement.jti = rotations.replacement_jti
         AND replacement.user_id = rotations.user_id
        WHERE rotations.source_jti = ?
          AND rotations.user_id = ?
          AND rotations.source_password_revision = ?
          AND rotations.source_expires_at_ms = ?
          AND rotations.recoverable_until_ms >= ?
          AND users.account_type = 'human'
          AND source.revoked_at_ms IS NOT NULL
          AND source.password_revision = rotations.source_password_revision
          AND source.created_at_ms = ?
          AND source.expires_at_ms = rotations.source_expires_at_ms
          AND replacement.revoked_at_ms IS NULL
          AND replacement.expires_at_ms > ?
          AND replacement.created_at_ms = rotations.replacement_issued_at_ms
          AND replacement.expires_at_ms = rotations.replacement_expires_at_ms
          AND replacement.password_revision = rotations.replacement_password_revision
          AND replacement.password_revision = users.password_revision
          AND NOT EXISTS (
              SELECT 1 FROM webui_session_rotations successor
              WHERE successor.source_jti = rotations.replacement_jti
          )
        """,
        (
            source_jti,
            user_id,
            source_password_revision,
            source_expires_at_ms,
            observed_at_ms,
            source_issued_at_ms,
            observed_at_ms,
        ),
    ).fetchone()
    user = normalize_user_row(dict(row)) if row is not None else None
    if row is None or user is None:
        return SessionRotationRecoveryState(status="terminal")
    user.pop("hashed_password", None)
    return SessionRotationRecoveryState(
        status="recovered",
        user=user,
        replacement_jti=str(row["replacement_jti"]),
        replacement_issued_at_ms=int(row["replacement_issued_at_ms"]),
        replacement_expires_at_ms=int(row["replacement_expires_at_ms"]),
        replacement_password_revision=int(row["replacement_password_revision"]),
        operation_id=str(row["operation_id"]),
    )


def _require_admitted_source(
    conn: sqlite3.Connection,
    user_id: int,
    source_jti: str,
    admitted_at_ms: int,
) -> None:
    row = conn.execute(
        """
        SELECT created_at_ms, expires_at_ms, revoked_at_ms
        FROM webui_device_sessions
        WHERE user_id = ? AND jti = ?
        """,
        (user_id, source_jti),
    ).fetchone()
    if row is None:
        rotation = conn.execute(
            """
            SELECT source_expires_at_ms, rotated_at_ms
            FROM webui_session_rotations
            WHERE user_id = ? AND source_jti = ?
            """,
            (user_id, source_jti),
        ).fetchone()
        if (
            rotation is None
            or admitted_at_ms > int(rotation["rotated_at_ms"])
            or admitted_at_ms >= int(rotation["source_expires_at_ms"])
        ):
            raise StateError("Authenticated session lineage source is missing.")
        return
    revoked_at_ms = row["revoked_at_ms"]
    if (
        int(row["created_at_ms"]) > admitted_at_ms
        or int(row["expires_at_ms"]) <= admitted_at_ms
        or (revoked_at_ms is not None and int(revoked_at_ms) < admitted_at_ms)
    ):
        raise StateError("Authenticated session was not active when admitted.")


def _sync_revoke_resolved_lineage(
    conn: sqlite3.Connection,
    user_id: int,
    source_jti: str,
    observed_at_ms: int,
    deadline_monotonic: float,
    invalidation_reason: str,
) -> SessionLineageRevocationResult:
    if time.monotonic() > deadline_monotonic:
        raise StateError("Session revocation deadline expired before execution.")
    terminal_jti = sync_resolve_terminal_session_jti(conn, user_id, source_jti)
    user_row = conn.execute(
        """
        SELECT username, password_revision FROM webui_users
        WHERE id = ? AND account_type = 'human'
        """,
        (user_id,),
    ).fetchone()
    terminal_row = conn.execute(
        """
        SELECT user_id, created_at_ms, revoked_at_ms, password_revision
        FROM webui_device_sessions WHERE jti = ?
        """,
        (terminal_jti,),
    ).fetchone()
    if user_row is None or terminal_row is None:
        raise StateError("WebUI session lineage terminal state is missing.")
    if int(terminal_row["user_id"]) != user_id:
        raise StateError("WebUI session lineage terminal ownership is invalid.")
    if terminal_row["revoked_at_ms"] is None and int(terminal_row["password_revision"]) != int(
        user_row["password_revision"]
    ):
        raise StateError("WebUI session lineage terminal revision is invalid.")
    revoked_jtis: tuple[str, ...] = ()
    if terminal_row["revoked_at_ms"] is None:
        revoked_at_ms = max(observed_at_ms, int(terminal_row["created_at_ms"]))
        updated = conn.execute(
            """
            UPDATE webui_device_sessions SET revoked_at_ms = ?
            WHERE user_id = ? AND jti = ? AND revoked_at_ms IS NULL
            """,
            (revoked_at_ms, user_id, terminal_jti),
        ).rowcount
        if updated == 1:
            revoked_jtis = (terminal_jti,)
    if time.monotonic() > deadline_monotonic:
        raise StateError("Session revocation deadline expired during execution.")
    username = str(user_row["username"])
    if revoked_jtis:
        sync_enqueue_user_domain_event(
            conn,
            event_type="UserSessionInvalidatedEvent",
            created_at_ms=observed_at_ms,
            user_id=user_id,
            username=username,
            invalidation_reason=invalidation_reason,
            session_jtis=revoked_jtis,
        )
    return SessionLineageRevocationResult(
        username=username,
        revoked_jtis=revoked_jtis,
    )


def sync_revoke_session_lineage(
    conn: sqlite3.Connection,
    user_id: int,
    source_jti: str,
    admitted_at_ms: int,
    deadline_monotonic: float,
) -> SessionLineageRevocationResult:
    observed_at_ms = epoch_ms()
    if observed_at_ms < admitted_at_ms:
        raise StateError("Session revocation chronology is invalid.")
    _require_admitted_source(conn, user_id, source_jti, admitted_at_ms)
    return _sync_revoke_resolved_lineage(
        conn,
        user_id,
        source_jti,
        observed_at_ms,
        deadline_monotonic,
        "logout",
    )


def sync_revoke_owned_session_lineage(
    conn: sqlite3.Connection,
    user_id: int,
    source_jti: str,
    deadline_monotonic: float,
) -> SessionLineageRevocationResult | None:
    owned = conn.execute(
        """
        SELECT 1 FROM webui_device_sessions WHERE user_id = ? AND jti = ?
        UNION ALL
        SELECT 1 FROM webui_session_rotations WHERE user_id = ? AND source_jti = ?
        LIMIT 1
        """,
        (user_id, source_jti, user_id, source_jti),
    ).fetchone()
    if owned is None:
        return None
    return _sync_revoke_resolved_lineage(
        conn,
        user_id,
        source_jti,
        epoch_ms(),
        deadline_monotonic,
        "session_revoked",
    )


def sync_revoke_all_user_sessions(
    conn: sqlite3.Connection,
    user_id: int,
    deadline_monotonic: float,
) -> SessionLineageRevocationResult:
    if time.monotonic() > deadline_monotonic:
        raise StateError("Session revocation deadline expired before execution.")
    user_row = conn.execute(
        """
        SELECT username FROM webui_users
        WHERE id = ? AND account_type = 'human'
        """,
        (user_id,),
    ).fetchone()
    if user_row is None:
        raise StateError("WebUI session owner is missing.")
    observed_at_ms = epoch_ms()
    revoked_jtis = sync_revoke_active_user_sessions(
        conn,
        user_id=user_id,
        revoked_at_ms=observed_at_ms,
    )
    if time.monotonic() > deadline_monotonic:
        raise StateError("Session revocation deadline expired during execution.")
    username = str(user_row["username"])
    if revoked_jtis:
        sync_enqueue_user_domain_event(
            conn,
            event_type="UserSessionInvalidatedEvent",
            created_at_ms=observed_at_ms,
            user_id=user_id,
            username=username,
            invalidation_reason="all_sessions_revoked",
            session_jtis=revoked_jtis,
        )
    if time.monotonic() > deadline_monotonic:
        raise StateError("Session revocation deadline expired during execution.")
    return SessionLineageRevocationResult(
        username=username,
        revoked_jtis=revoked_jtis,
    )


__all__ = (
    "sync_recover_session_rotation",
    "sync_revoke_all_user_sessions",
    "sync_revoke_owned_session_lineage",
    "sync_revoke_session_lineage",
)

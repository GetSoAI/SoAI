"""SoAI - WebUI device session registration and activity writes [backend/database/repositories/users/webui_session_registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import Never

from core.auth.webui_sessions import (
    WEBUI_SESSION_TOUCH_INTERVAL_MS,
    WebuiSessionDescriptor,
    WebuiSessionJtiCollisionError,
    WebuiSessionRegistrationResult,
)
from core.errors.exceptions import DatabaseError
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.webui_identity_maintenance import (
    sync_prune_expired_session_lineage_state,
)
from database.repositories.users.webui_session_writes import sync_revoke_session_rows


def raise_classified_webui_session_registration_error(
    exception: sqlite3.IntegrityError | DatabaseError,
) -> Never:
    integrity_error = (
        exception
        if isinstance(exception, sqlite3.IntegrityError)
        else exception.cause if isinstance(exception.cause, sqlite3.IntegrityError) else None
    )
    if integrity_error is None:
        raise exception
    constraint_type, detail = parse_sqlite_integrity_error(integrity_error)
    if constraint_type == "unique" and detail == "webui_device_sessions.jti":
        raise WebuiSessionJtiCollisionError(
            "A generated WebUI session identity collided.",
            cause=exception,
        ) from exception
    raise exception


def sync_register_webui_session(
    conn: sqlite3.Connection,
    jti: str,
    expected_user_id: int,
    username: str,
    expected_password_revision: int,
    descriptor: WebuiSessionDescriptor,
    issued_at_ms: int,
    expires_at_ms: int,
) -> WebuiSessionRegistrationResult | None:
    sync_prune_expired_session_lineage_state(conn, issued_at_ms)
    user_row = conn.execute(
        """
        SELECT id, password_revision FROM webui_users
        WHERE id = ? AND username = ? AND account_type = 'human'
        """,
        (expected_user_id, username),
    ).fetchone()
    if user_row is None or int(user_row["password_revision"]) != expected_password_revision:
        return None
    revoked_jtis: tuple[str, ...] = ()
    if descriptor.device_id is not None:
        previous_rows = tuple(
            conn.execute(
                """
                SELECT jti, expires_at_ms, created_at_ms FROM webui_device_sessions
                WHERE user_id = ? AND device_id = ? AND revoked_at_ms IS NULL
                """,
                (expected_user_id, descriptor.device_id),
            ).fetchall()
        )
        revoked_jtis = sync_revoke_session_rows(conn, previous_rows, issued_at_ms)
    conn.execute(
        """
        INSERT INTO webui_device_sessions (
            jti, user_id, device_id, device_label, client_type, user_agent,
            password_revision, created_at_ms, last_seen_at_ms, expires_at_ms, revoked_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            jti,
            expected_user_id,
            descriptor.device_id,
            descriptor.device_label,
            descriptor.client_type,
            descriptor.user_agent,
            expected_password_revision,
            issued_at_ms,
            issued_at_ms,
            expires_at_ms,
        ),
    )
    return WebuiSessionRegistrationResult(
        jti=jti,
        user_id=expected_user_id,
        revoked_jtis=revoked_jtis,
    )


def sync_touch_webui_session(
    conn: sqlite3.Connection,
    jti: str,
    observed_at_ms: int,
) -> bool:
    return (
        conn.execute(
            """
        UPDATE webui_device_sessions SET last_seen_at_ms = ?
        WHERE jti = ? AND revoked_at_ms IS NULL AND expires_at_ms > ?
          AND last_seen_at_ms <= ?
        """,
            (
                observed_at_ms,
                jti,
                observed_at_ms,
                observed_at_ms - WEBUI_SESSION_TOUCH_INTERVAL_MS,
            ),
        ).rowcount
        > 0
    )


def sync_rename_android_webui_session(
    conn: sqlite3.Connection,
    user_id: int,
    jti: str,
    device_id: str,
    device_label: str,
    observed_at_ms: int,
) -> bool:
    return (
        conn.execute(
            """
        UPDATE webui_device_sessions SET device_label = ?
        WHERE user_id = ? AND jti = ? AND device_id = ? AND client_type = 'android'
          AND revoked_at_ms IS NULL AND expires_at_ms > ?
        """,
            (device_label, user_id, jti, device_id, observed_at_ms),
        ).rowcount
        > 0
    )


__all__ = (
    "raise_classified_webui_session_registration_error",
    "sync_register_webui_session",
    "sync_rename_android_webui_session",
    "sync_touch_webui_session",
)

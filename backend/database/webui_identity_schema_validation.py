"""SoAI - V1 WebUI identity row validation [backend/database/webui_identity_schema_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import time

from core.errors.exceptions import StateError
from core.users.account_types import HUMAN_ACCOUNT_TYPE
from core.users.username import require_canonical_username
from core.workspaces.user_workspace_path import require_default_workspace_path
from database.repositories.users.webui_session_lineage_validation import (
    sync_validate_rotation_lineages,
)


def _validate_account_rows(conn: sqlite3.Connection) -> None:
    rows = conn.execute("""
        SELECT id, username, account_type, is_admin, workspace_path,
               default_workspace_path, password_revision, identity_revision
        FROM webui_users
        ORDER BY id
        """).fetchall()
    for row in rows:
        user_id = int(row[0])
        username = str(row[1])
        account_type = str(row[2])
        if require_canonical_username(username) != username:
            raise StateError("WebUI account username is not canonical.")
        if account_type != HUMAN_ACCOUNT_TYPE:
            raise StateError("WebUI account type is invalid.")
        require_default_workspace_path(str(row[5]), owner_user_id=user_id)
        if not str(row[4]) or int(row[6]) < 1 or int(row[7]) < 1:
            raise StateError("WebUI account identity fields are invalid.")


def _validate_chronology(conn: sqlite3.Connection) -> None:
    now_ms = int(time.time() * 1000)
    row = conn.execute(
        """
        SELECT max(value)
        FROM (
            SELECT max(created_at_ms) AS value
            FROM webui_device_sessions
            WHERE expires_at_ms > ?
            UNION ALL
            SELECT max(rotated_at_ms) AS value
            FROM webui_session_rotations
            WHERE source_expires_at_ms > ?
               OR replacement_expires_at_ms > ?
               OR recoverable_until_ms > ?
        )
        """,
        (now_ms, now_ms, now_ms, now_ms),
    ).fetchone()
    if row is not None and row[0] is not None and now_ms < int(row[0]):
        raise StateError("System clock precedes active WebUI session chronology.")


def _validate_pending_password_outbox_payloads(conn: sqlite3.Connection) -> None:
    row = conn.execute("""
        SELECT id
        FROM webui_domain_event_outbox
        WHERE status IN ('pending', 'processing')
          AND event_type = 'UserPasswordChangedEvent'
          AND (
              coalesce(json_type(payload_json, '$.operation_id'), 'missing') != 'text'
              OR coalesce(json_type(payload_json, '$.actor_user_id'), 'missing') != 'integer'
              OR coalesce(json_type(payload_json, '$.revoked_session_jtis'), 'missing') != 'array'
              OR coalesce(json_type(payload_json, '$.rotation_source_jti'), 'missing')
                    NOT IN ('text', 'null')
          )
        LIMIT 1
        """).fetchone()
    if row is not None:
        raise StateError("Pending password event payload predates the current V1 contract.")


def validate_current_v1_webui_identity_rows(conn: sqlite3.Connection) -> None:
    _validate_account_rows(conn)
    _validate_chronology(conn)
    sync_validate_rotation_lineages(conn, int(time.time() * 1000))
    _validate_pending_password_outbox_payloads(conn)


__all__ = ("validate_current_v1_webui_identity_rows",)

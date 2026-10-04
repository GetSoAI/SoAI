"""SoAI - V1 WebUI identity row validation [backend/database/webui_identity_schema_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.users.account_types import HUMAN_ACCOUNT_TYPE
from core.users.username import require_canonical_username
from core.workspaces.user_workspace_path import require_default_workspace_path
from database.core.savepoints import SQLiteSavepoint
from database.repositories.users.webui_identity_maintenance import (
    sync_prune_future_session_lineage_state,
)
from database.repositories.users.webui_session_lineage_validation import (
    sync_validate_rotation_lineages,
)

LOGGER_NAME = "SoAI.database.webui_identity_schema_validation"


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


def validate_current_webui_identity_rows(conn: sqlite3.Connection) -> None:
    observed_at_ms = epoch_ms()
    with SQLiteSavepoint(conn, "validate_webui_identity_rows"):
        _validate_account_rows(conn)
        pruned = sync_prune_future_session_lineage_state(conn, observed_at_ms)
        sync_validate_rotation_lineages(conn, observed_at_ms)
        _validate_pending_password_outbox_payloads(conn)
    if pruned.session_count or pruned.rotation_count:
        get_logger(LOGGER_NAME).warning(
            "Removed %s WebUI sessions and %s session rotations dated after the system clock; affected users must sign in again.",
            pruned.session_count,
            pruned.rotation_count,
        )


__all__ = ("validate_current_webui_identity_rows",)

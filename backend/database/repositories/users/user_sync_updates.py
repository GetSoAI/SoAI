"""SoAI - User update and delete sync database operations [backend/database/repositories/users/user_sync_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.openai.model_settings_validation import validate_model_settings
from core.serialization.json import serialize_json_compact_stable_strict
from core.state.errors import CannotDeleteLastAdminError, CannotDemoteLastAdminError
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from core.workspaces.conversation_workspace_path import (
    resolve_conversation_workspace_path_override_with_user_root,
)
from database.repositories.users.api_keys.assignment_ops import (
    sync_revoke_assigned_keys_for_user,
)
from database.repositories.users.conversation_deletion_operations import (
    sync_delete_all_conversations,
)
from database.repositories.users.user_event_outbox import sync_enqueue_user_domain_event
from database.repositories.users.user_field_coercion import coerce_user_admin_flag
from database.repositories.users.user_sync_queries import (
    sync_count_human_admins,
    sync_get_human_user_by_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_clear_user_preferences",
    "sync_delete_user",
    "sync_update_user_role",
    "sync_update_user_workspace_path",
)


def _require_identity_revision(user: JSONDict) -> int:
    value = user.get("identity_revision")
    if not is_strict_int(value) or int(value) < 1:
        raise StateError("Updated user identity revision is invalid.")
    return int(value)


def _revoke_invalid_conversation_workspace_overrides(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    allowed_root_real_path: str,
) -> int:
    allowed_root = os.path.realpath(os.path.abspath(str(allowed_root_real_path or "").strip()))
    if not allowed_root:
        raise StateError("Allowed root path is required for override revocation.")
    cursor = conn.execute(
        "SELECT id, model_settings FROM webui_conversations WHERE user_id = ?",
        (user_id,),
    )
    revoked = 0
    rows = cursor.fetchall()
    for row in rows:
        conv_id_value = row[0] if row else None
        model_settings_value = row[1] if row[1:2] else None
        if not isinstance(conv_id_value, str) or not conv_id_value.strip():
            continue
        settings = validate_model_settings(model_settings_value)
        workspace_override_value = settings.get("workspace_path")
        if not isinstance(workspace_override_value, str) or not workspace_override_value.strip():
            continue
        override_is_valid = True
        try:
            resolve_conversation_workspace_path_override_with_user_root(
                user_root_real=allowed_root,
                override_workspace_path=workspace_override_value,
                require_existing_directories=True,
            )
        except ValidationError:
            override_is_valid = False
        if override_is_valid:
            continue
        updated_settings = dict(settings)
        updated_settings.pop("workspace_path", None)
        conn.execute(
            "UPDATE webui_conversations SET model_settings = ? WHERE id = ? AND user_id = ?",
            (serialize_json_compact_stable_strict(updated_settings), conv_id_value, user_id),
        )
        revoked += 1
    return revoked


def sync_update_user_role(
    conn: sqlite3.Connection,
    user_id: int,
    is_admin: bool,
) -> JSONDict | None:
    current_user = sync_get_human_user_by_id(conn, user_id)
    if current_user is None:
        return None
    current_is_admin = coerce_user_admin_flag(current_user.get("is_admin"))
    requested_is_admin = bool(is_admin)
    if current_is_admin == requested_is_admin:
        return current_user
    if current_is_admin and (not requested_is_admin) and sync_count_human_admins(conn) <= 1:
        raise CannotDemoteLastAdminError(
            "Cannot remove administrator role from the last administrator.",
        )
    updated = (
        conn.execute(
            """
            UPDATE webui_users
            SET is_admin = ?, identity_revision = identity_revision + 1
            WHERE id = ? AND account_type = 'human' AND is_admin != ?
            """,
            (int(requested_is_admin), user_id, int(requested_is_admin)),
        ).rowcount
        > 0
    )
    if not updated:
        return None
    now = epoch_ms()
    updated_user = sync_get_human_user_by_id(conn, user_id)
    if updated_user is None:
        raise StateError("User role updated but user row could not be reloaded.")
    sync_enqueue_user_domain_event(
        conn,
        event_type="UserRoleChangedEvent",
        created_at_ms=now,
        user_id=user_id,
        username=str(updated_user.get("username") or ""),
        is_admin=requested_is_admin,
        identity_revision=_require_identity_revision(updated_user),
    )
    return updated_user


def sync_update_user_workspace_path(
    conn: sqlite3.Connection,
    user_id: int,
    workspace_path: str | None,
    workspace_real_path: str,
) -> JSONDict | None:
    current_user = sync_get_human_user_by_id(conn, user_id)
    if current_user is None:
        return None
    if workspace_path is None or not str(workspace_path).strip():
        default_workspace_value = current_user.get("default_workspace_path")
        if not isinstance(default_workspace_value, str) or not default_workspace_value:
            raise StateError("User default workspace is invalid.")
        workspace_path_value = default_workspace_value
    else:
        workspace_path_value = str(workspace_path).strip()
    if current_user.get("workspace_path") == workspace_path_value:
        return current_user
    updated = (
        conn.execute(
            """
            UPDATE webui_users
            SET workspace_path = ?, identity_revision = identity_revision + 1
            WHERE id = ? AND account_type = 'human' AND workspace_path != ?
            """,
            (workspace_path_value, user_id, workspace_path_value),
        ).rowcount
        > 0
    )
    if not updated:
        return None
    _revoke_invalid_conversation_workspace_overrides(
        conn,
        user_id=user_id,
        allowed_root_real_path=workspace_real_path,
    )
    return sync_get_human_user_by_id(conn, user_id)


def sync_delete_user(conn: sqlite3.Connection, user_id: int) -> bool:
    user = sync_get_human_user_by_id(conn, user_id)
    if user is None:
        return False
    if coerce_user_admin_flag(user.get("is_admin")) and sync_count_human_admins(conn) <= 1:
        raise CannotDeleteLastAdminError("Cannot delete the last administrator.")
    now = epoch_ms()
    sync_revoke_assigned_keys_for_user(conn, user_id, now)
    sync_delete_all_conversations(conn, user_id)
    deleted = (
        conn.execute(
            "DELETE FROM webui_users WHERE id = ? AND account_type = 'human'",
            (user_id,),
        ).rowcount
        > 0
    )
    if not deleted:
        raise StateError("User disappeared during the deletion transaction.")
    sync_enqueue_user_domain_event(
        conn,
        event_type="UserDeletedEvent",
        created_at_ms=now,
        user_id=user_id,
        username=str(user.get("username") or ""),
    )
    return True


def sync_clear_user_preferences(conn: sqlite3.Connection, user_id: int) -> bool:
    return (
        conn.execute(
            """
            UPDATE webui_users SET preferences = NULL
            WHERE id = ? AND account_type = 'human'
            """,
            (user_id,),
        ).rowcount
        > 0
    )

"""SoAI - Database matching for immutable user identity snapshots [backend/database/repositories/users/user_identity_snapshot_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.users.account_types import HUMAN_ACCOUNT_TYPE
from core.users.username_rename import UserIdentitySnapshot


def sync_identity_snapshot_matches(
    row: sqlite3.Row | None,
    snapshot: UserIdentitySnapshot,
) -> bool:
    return row is not None and (
        int(row["id"]) == snapshot.user_id
        and str(row["username"]) == snapshot.username
        and str(row["account_type"]) == HUMAN_ACCOUNT_TYPE
        and bool(row["is_admin"]) is snapshot.is_admin
        and str(row["workspace_path"]) == snapshot.workspace_path
        and str(row["default_workspace_path"]) == snapshot.default_workspace_path
        and int(row["identity_revision"]) == snapshot.identity_revision
        and str(row["hashed_password"]) == snapshot.hashed_password
        and int(row["password_revision"]) == snapshot.password_revision
        and int(row["password_changed_at_ms"]) == snapshot.password_changed_at_ms
    )


def sync_actor_identity_snapshot_matches(
    row: sqlite3.Row | None,
    snapshot: UserIdentitySnapshot,
    *,
    self_mutation: bool,
) -> bool:
    if self_mutation:
        return sync_identity_snapshot_matches(row, snapshot)
    return row is not None and (
        int(row["id"]) == snapshot.user_id
        and str(row["username"]) == snapshot.username
        and str(row["account_type"]) == HUMAN_ACCOUNT_TYPE
        and bool(row["is_admin"]) is snapshot.is_admin
        and str(row["hashed_password"]) == snapshot.hashed_password
        and int(row["password_revision"]) == snapshot.password_revision
        and int(row["password_changed_at_ms"]) == snapshot.password_changed_at_ms
    )


__all__ = ("sync_actor_identity_snapshot_matches", "sync_identity_snapshot_matches")

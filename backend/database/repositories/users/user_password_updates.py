"""SoAI - Transactional human password mutation operations [backend/database/repositories/users/user_password_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import time

from core.errors.exceptions import StateError
from core.mutations.identifiers import create_mutation_request_id
from core.timing.epoch import epoch_ms
from core.users.password_change import PasswordChangeDatabaseResult, PasswordChangeTransaction
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.repositories.users.identity_mutation_chronology import (
    sync_identity_mutation_chronology_is_valid,
)
from database.repositories.users.identity_mutation_record_storage import (
    sync_insert_committed_password_mutation,
    sync_insert_failed_identity_mutation,
    sync_read_identity_mutation,
)
from database.repositories.users.password_session_rotation import (
    sync_insert_password_session_successor,
)
from database.repositories.users.user_event_outbox import sync_enqueue_user_domain_event
from database.repositories.users.user_identity_snapshot_matching import (
    sync_actor_identity_snapshot_matches,
    sync_identity_snapshot_matches,
)
from database.repositories.users.user_sync_queries import sync_get_human_user_by_id
from database.repositories.users.webui_session_writes import sync_revoke_active_user_sessions


def sync_update_user_password(
    conn: sqlite3.Connection,
    username: str,
    new_hashed_password: str,
) -> bool:
    observed_at_ms = epoch_ms()
    row = conn.execute(
        """
        SELECT id, password_revision FROM webui_users
        WHERE username = ? AND account_type = 'human'
        """,
        (username,),
    ).fetchone()
    if row is None or int(row["password_revision"]) >= JAVASCRIPT_SAFE_INTEGER_MAX:
        return False
    user_id = int(row["id"])
    previous_revision = int(row["password_revision"])
    updated = conn.execute(
        """
        UPDATE webui_users
        SET hashed_password = ?, password_changed_at_ms = ?,
            password_revision = password_revision + 1
        WHERE id = ? AND account_type = 'human' AND password_revision = ?
        """,
        (new_hashed_password, observed_at_ms, user_id, previous_revision),
    ).rowcount
    if updated != 1:
        return False
    revoked_jtis = sync_revoke_active_user_sessions(
        conn,
        user_id=user_id,
        revoked_at_ms=observed_at_ms,
    )
    sync_enqueue_user_domain_event(
        conn,
        event_type="UserPasswordChangedEvent",
        created_at_ms=observed_at_ms,
        user_id=user_id,
        username=username,
        operation_id=create_mutation_request_id(),
        actor_user_id=user_id,
        password_revision=previous_revision + 1,
        revoked_session_jtis=revoked_jtis,
        rotation_source_jti=None,
    )
    return True


def _failed(
    conn: sqlite3.Connection,
    transaction: PasswordChangeTransaction,
    error_code: str,
) -> PasswordChangeDatabaseResult:
    record = sync_insert_failed_identity_mutation(
        conn,
        transaction.binding,
        error_code,
        None,
    )
    return PasswordChangeDatabaseResult(
        record=record,
        revoked_jtis=(),
        user=None,
        committed_now=False,
    )


def _source_row(
    conn: sqlite3.Connection,
    transaction: PasswordChangeTransaction,
    observed_at_ms: int,
) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT * FROM webui_device_sessions
        WHERE jti = ? AND user_id = ? AND revoked_at_ms IS NULL
          AND expires_at_ms > ? AND password_revision = ?
        """,
        (
            transaction.source_jti,
            transaction.actor.user_id,
            observed_at_ms,
            transaction.actor.password_revision,
        ),
    ).fetchone()
    if row is not None and not isinstance(row, sqlite3.Row):
        raise StateError("Password mutation source session row has an invalid type.")
    descriptor = transaction.source_descriptor
    if row is None or descriptor is None:
        return row
    if row["device_id"] != descriptor.device_id:
        return None
    if str(row["device_label"]) != descriptor.device_label:
        return None
    if str(row["client_type"]) != descriptor.client_type:
        return None
    if str(row["user_agent"]) != descriptor.user_agent:
        return None
    return row


def sync_change_user_password(
    conn: sqlite3.Connection,
    transaction: PasswordChangeTransaction,
) -> PasswordChangeDatabaseResult:
    existing = sync_read_identity_mutation(conn, transaction.binding)
    if existing is not None:
        return PasswordChangeDatabaseResult(
            record=existing,
            revoked_jtis=(),
            user=None,
            committed_now=False,
        )
    if time.monotonic() >= transaction.deadline_monotonic:
        return _failed(conn, transaction, "identity_mutation_deadline_exceeded")
    observed_at_ms = epoch_ms()
    if not sync_identity_mutation_chronology_is_valid(conn, observed_at_ms):
        return _failed(conn, transaction, "identity_mutation_time_invalid")
    actor_row = conn.execute(
        "SELECT * FROM webui_users WHERE id = ? AND account_type = 'human'",
        (transaction.actor.user_id,),
    ).fetchone()
    target_row = conn.execute(
        "SELECT * FROM webui_users WHERE id = ? AND account_type = 'human'",
        (transaction.target.user_id,),
    ).fetchone()
    is_self = transaction.actor.user_id == transaction.target.user_id
    if not sync_actor_identity_snapshot_matches(
        actor_row,
        transaction.actor,
        self_mutation=is_self,
    ) or not sync_identity_snapshot_matches(target_row, transaction.target):
        return _failed(conn, transaction, "user_state_conflict")
    if not is_self and not transaction.actor.is_admin:
        return _failed(conn, transaction, "user_state_conflict")
    source_row = _source_row(conn, transaction, observed_at_ms)
    if source_row is None:
        return _failed(conn, transaction, "user_state_conflict")
    successor = transaction.successor
    if is_self and (
        successor is None
        or int(source_row["expires_at_ms"]) < transaction.recovery_horizon_at_ms
        or successor.expires_at_ms < transaction.recovery_horizon_at_ms
    ):
        return _failed(conn, transaction, "session_rotation_window_unavailable")
    if successor is not None and successor.issued_at_ms > observed_at_ms:
        return _failed(conn, transaction, "identity_mutation_time_invalid")
    changed_at_ms = successor.issued_at_ms if successor is not None else observed_at_ms
    updated = conn.execute(
        """
        UPDATE webui_users
        SET hashed_password = ?, password_changed_at_ms = ?,
            password_revision = password_revision + 1
        WHERE id = ? AND account_type = 'human' AND username = ?
          AND hashed_password = ? AND password_revision = ?
          AND password_changed_at_ms = ? AND identity_revision = ?
          AND workspace_path = ? AND default_workspace_path = ?
          AND is_admin = ? AND password_revision < ?
        """,
        (
            transaction.new_hashed_password,
            changed_at_ms,
            transaction.target.user_id,
            transaction.target.username,
            transaction.target.hashed_password,
            transaction.target.password_revision,
            transaction.target.password_changed_at_ms,
            transaction.target.identity_revision,
            transaction.target.workspace_path,
            transaction.target.default_workspace_path,
            int(transaction.target.is_admin),
            JAVASCRIPT_SAFE_INTEGER_MAX,
        ),
    ).rowcount
    if updated != 1:
        return _failed(conn, transaction, "user_state_conflict")
    revoked_jtis = sync_revoke_active_user_sessions(
        conn,
        user_id=transaction.target.user_id,
        revoked_at_ms=observed_at_ms,
    )
    rotation_source_jti: str | None = None
    rotation_cleanup_at_ms: int | None = None
    if is_self:
        if revoked_jtis.count(transaction.source_jti) != 1:
            raise StateError("Self password change did not revoke its exact source session.")
        rotation_cleanup_at_ms = sync_insert_password_session_successor(
            conn,
            transaction,
            source_row,
            observed_at_ms,
        )
        rotation_source_jti = transaction.source_jti
    new_revision = transaction.target.password_revision + 1
    record = sync_insert_committed_password_mutation(
        conn,
        transaction.binding,
        completed_at_ms=observed_at_ms,
        previous_password_revision=transaction.target.password_revision,
        new_password_revision=new_revision,
        rotation_cleanup_at_ms=rotation_cleanup_at_ms,
    )
    updated_user = sync_get_human_user_by_id(conn, transaction.target.user_id)
    if updated_user is None:
        raise StateError("Updated password user could not be loaded.")
    sync_enqueue_user_domain_event(
        conn,
        event_type="UserPasswordChangedEvent",
        created_at_ms=observed_at_ms,
        user_id=transaction.target.user_id,
        username=transaction.target.username,
        operation_id=transaction.binding.operation_id,
        actor_user_id=transaction.actor.user_id,
        password_revision=new_revision,
        revoked_session_jtis=revoked_jtis,
        rotation_source_jti=rotation_source_jti,
    )
    if time.monotonic() >= transaction.deadline_monotonic:
        raise TimeoutError("Password mutation deadline expired before commit.")
    return PasswordChangeDatabaseResult(
        record=record,
        revoked_jtis=revoked_jtis,
        user=updated_user,
        committed_now=True,
    )


__all__ = ("sync_change_user_password", "sync_update_user_password")

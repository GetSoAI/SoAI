"""SoAI - Atomic username rename transaction [backend/database/repositories/users/username_rename_transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import time

from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.users.identity_mutation_contract import SESSION_LINEAGE_PRUNE_GRACE_MS
from core.users.username_rename import (
    UsernameRenameDatabaseResult,
    UsernameRenameTransaction,
)
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.identity_mutation_chronology import (
    sync_identity_mutation_chronology_is_valid,
)
from database.repositories.users.identity_mutation_record_storage import (
    sync_insert_committed_username_mutation,
    sync_insert_failed_identity_mutation,
    sync_read_identity_mutation,
)
from database.repositories.users.user_event_outbox import sync_enqueue_user_domain_event
from database.repositories.users.user_identity_snapshot_matching import (
    sync_actor_identity_snapshot_matches,
    sync_identity_snapshot_matches,
)
from database.repositories.users.username_auth_bucket_cleanup import (
    sync_clear_username_auth_buckets,
)
from database.repositories.users.webui_session_writes import (
    sync_revoke_active_user_sessions,
)


def _failed(
    conn: sqlite3.Connection,
    transaction: UsernameRenameTransaction,
    error_code: str,
) -> UsernameRenameDatabaseResult:
    record = sync_insert_failed_identity_mutation(
        conn,
        transaction.binding,
        error_code,
        None,
    )
    return UsernameRenameDatabaseResult(record=record, revoked_jtis=(), committed_now=False)


def sync_rename_username(
    conn: sqlite3.Connection,
    transaction: UsernameRenameTransaction,
) -> UsernameRenameDatabaseResult:
    existing = sync_read_identity_mutation(conn, transaction.binding)
    if existing is not None:
        return UsernameRenameDatabaseResult(
            record=existing,
            revoked_jtis=(),
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
    ) or not sync_identity_snapshot_matches(
        target_row,
        transaction.target,
    ):
        return _failed(conn, transaction, "user_state_conflict")
    if not is_self and not transaction.actor.is_admin:
        return _failed(conn, transaction, "user_state_conflict")
    requested_username = transaction.binding.requested_username
    if requested_username is None:
        raise StateError("Username rename binding lost its requested username.")
    if requested_username == transaction.target.username:
        return _failed(conn, transaction, "username_unchanged")
    owner = conn.execute(
        "SELECT id FROM webui_users WHERE username = ?",
        (requested_username,),
    ).fetchone()
    if owner is not None and int(owner["id"]) != transaction.target.user_id:
        return _failed(conn, transaction, "username_conflict")
    source_row = conn.execute(
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
    if source_row is None:
        return _failed(conn, transaction, "user_state_conflict")
    if transaction.source_descriptor is not None and (
        source_row["device_id"] != transaction.source_descriptor.device_id
        or str(source_row["device_label"]) != transaction.source_descriptor.device_label
        or str(source_row["client_type"]) != transaction.source_descriptor.client_type
        or str(source_row["user_agent"]) != transaction.source_descriptor.user_agent
    ):
        return _failed(conn, transaction, "user_state_conflict")
    if is_self:
        successor = transaction.successor
        if successor is None:
            raise StateError("Self rename requires a successor credential.")
        if (
            int(source_row["expires_at_ms"]) < transaction.recovery_horizon_at_ms
            or successor.expires_at_ms < transaction.recovery_horizon_at_ms
        ):
            return _failed(conn, transaction, "session_rotation_window_unavailable")
        if successor.issued_at_ms > observed_at_ms:
            return _failed(conn, transaction, "identity_mutation_time_invalid")
    try:
        updated = conn.execute(
            """
            UPDATE webui_users
            SET username = ?, identity_revision = identity_revision + 1
            WHERE id = ? AND account_type = 'human'
              AND username = ? AND identity_revision = ?
              AND identity_revision < ?
            """,
            (
                requested_username,
                transaction.target.user_id,
                transaction.target.username,
                transaction.target.identity_revision,
                JAVASCRIPT_SAFE_INTEGER_MAX,
            ),
        ).rowcount
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type == "unique" and detail == "webui_users.username":
            collision_owner = conn.execute(
                "SELECT id FROM webui_users WHERE username = ?",
                (requested_username,),
            ).fetchone()
            if (
                collision_owner is not None
                and int(collision_owner["id"]) != transaction.target.user_id
            ):
                return _failed(conn, transaction, "username_conflict")
        raise
    if updated != 1:
        return _failed(conn, transaction, "user_state_conflict")
    sync_clear_username_auth_buckets(conn, transaction.target.username)
    sync_clear_username_auth_buckets(conn, requested_username)
    revoked_jtis = sync_revoke_active_user_sessions(
        conn,
        user_id=transaction.target.user_id,
        revoked_at_ms=observed_at_ms,
    )
    rotation_source_jti: str | None = None
    rotation_cleanup_at_ms: int | None = None
    if is_self:
        successor = transaction.successor
        if successor is None or transaction.source_descriptor is None:
            raise StateError("Self rename session preparation is incomplete.")
        if revoked_jtis.count(transaction.source_jti) != 1:
            raise StateError("Self rename did not revoke its exact source session.")
        descriptor = transaction.source_descriptor
        conn.execute(
            """
            INSERT INTO webui_device_sessions (
                jti, user_id, device_id, device_label, client_type, user_agent,
                password_revision, created_at_ms, last_seen_at_ms, expires_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                successor.jti,
                transaction.actor.user_id,
                descriptor.device_id,
                descriptor.device_label,
                descriptor.client_type,
                descriptor.user_agent,
                transaction.actor.password_revision,
                successor.issued_at_ms,
                successor.issued_at_ms,
                successor.expires_at_ms,
            ),
        )
        conn.execute(
            """
            INSERT INTO webui_session_rotations (
                source_jti, replacement_jti, operation_id, operation_type, user_id,
                source_password_revision, source_expires_at_ms,
                replacement_password_revision, replacement_issued_at_ms,
                replacement_expires_at_ms, rotated_at_ms, recoverable_until_ms
            ) VALUES (?, ?, ?, 'username_rename', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction.source_jti,
                successor.jti,
                transaction.binding.operation_id,
                transaction.actor.user_id,
                transaction.actor.password_revision,
                int(source_row["expires_at_ms"]),
                transaction.actor.password_revision,
                successor.issued_at_ms,
                successor.expires_at_ms,
                observed_at_ms,
                transaction.recovery_horizon_at_ms,
            ),
        )
        rotation_source_jti = transaction.source_jti
        rotation_cleanup_at_ms = (
            max(
                int(source_row["expires_at_ms"]),
                successor.expires_at_ms,
                transaction.recovery_horizon_at_ms,
            )
            + SESSION_LINEAGE_PRUNE_GRACE_MS
        )
    new_identity_revision = transaction.target.identity_revision + 1
    record = sync_insert_committed_username_mutation(
        conn,
        transaction.binding,
        previous_username=transaction.target.username,
        new_identity_revision=new_identity_revision,
        completed_at_ms=observed_at_ms,
        rotation_cleanup_at_ms=rotation_cleanup_at_ms,
    )
    sync_enqueue_user_domain_event(
        conn,
        event_type="UserUsernameChangedEvent",
        created_at_ms=observed_at_ms,
        user_id=transaction.target.user_id,
        username=requested_username,
        operation_id=transaction.binding.operation_id,
        actor_user_id=transaction.actor.user_id,
        previous_username=transaction.target.username,
        identity_revision=new_identity_revision,
        revoked_session_jtis=revoked_jtis,
        rotation_source_jti=rotation_source_jti,
    )
    if time.monotonic() >= transaction.deadline_monotonic:
        raise TimeoutError("Identity mutation deadline expired before commit.")
    return UsernameRenameDatabaseResult(
        record=record,
        revoked_jtis=revoked_jtis,
        committed_now=True,
    )


__all__ = ("sync_rename_username",)

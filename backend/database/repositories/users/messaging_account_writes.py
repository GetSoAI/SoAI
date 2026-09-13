"""SoAI - Atomic Messaging account mutations [backend/database/repositories/users/messaging_account_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.timing.epoch import epoch_ms
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.messaging_account_reads import sync_read_messaging_account
from database.repositories.users.messaging_delivery_fencing import (
    sync_fence_messaging_deliveries,
)
from database.repositories.users.messaging_interaction_fencing import (
    sync_fence_messaging_interactions,
)

if TYPE_CHECKING:
    from core.messaging.account_models import (
        MessagingAccountCreate,
        MessagingAccountLifecycleState,
        MessagingAccountUpdate,
        MessagingAuthorizedSender,
    )
    from core.types.json import JSONDict

__all__ = (
    "sync_create_messaging_account",
    "sync_set_messaging_account_lifecycle_state",
    "sync_update_messaging_account",
)


def _insert_senders(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    senders: tuple[MessagingAuthorizedSender, ...],
    now_ms: int,
) -> None:
    conn.executemany(
        """
        INSERT INTO messaging_authorized_senders (
            account_id, user_id, sender_id, display_label, created_at_ms, updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (account_id, user_id, sender.sender_id, sender.display_label, now_ms, now_ms)
            for sender in senders
        ],
    )


def _fence_removed_senders(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    senders: tuple[MessagingAuthorizedSender, ...],
    now_ms: int,
) -> None:
    retained = {sender.sender_id for sender in senders}
    existing_rows = conn.execute(
        """
        SELECT sender_id FROM messaging_authorized_senders
        WHERE account_id = ? AND user_id = ?
        """,
        (account_id, user_id),
    ).fetchall()
    removed = tuple(str(row[0]) for row in existing_rows if str(row[0]) not in retained)
    for sender_id in removed:
        sync_fence_messaging_interactions(
            conn,
            account_id=account_id,
            user_id=user_id,
            sender_id=sender_id,
            resolved_at_ms=now_ms,
        )
        sync_fence_messaging_deliveries(
            conn,
            account_id=account_id,
            user_id=user_id,
            sender_id=sender_id,
            failure_code="messaging_sender_revoked",
            now_ms=now_ms,
        )


def _fence_disabled_account(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    now_ms: int,
) -> None:
    sync_fence_messaging_interactions(
        conn,
        account_id=account_id,
        user_id=user_id,
        resolved_at_ms=now_ms,
    )
    sync_fence_messaging_deliveries(
        conn,
        account_id=account_id,
        user_id=user_id,
        failure_code="messaging_account_disabled",
        now_ms=now_ms,
    )


def sync_create_messaging_account(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
    account: MessagingAccountCreate,
    credential_ciphertext: str,
    credential_fingerprint: str,
    model_settings_json: str,
) -> JSONDict:
    now_ms = epoch_ms()
    try:
        conn.execute(
            """
            INSERT INTO messaging_accounts (
                account_id, user_id, platform, label, principal_id, principal_label,
                parent_principal_id, application_principal_id,
                credential_ciphertext, credential_fingerprint,
                model_settings_json, locale, lifecycle_state, revision,
                plaintext_secret_replies_enabled, accept_messages_from_anyone,
                created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                account_id,
                user_id,
                account.platform,
                account.label,
                account.principal_id,
                account.principal_label,
                account.parent_principal_id,
                account.application_principal_id,
                credential_ciphertext,
                credential_fingerprint,
                model_settings_json,
                account.locale,
                account.lifecycle_state,
                1 if account.plaintext_secret_replies_enabled else 0,
                1 if account.accept_messages_from_anyone else 0,
                now_ms,
                now_ms,
            ),
        )
        _insert_senders(
            conn,
            account_id=account_id,
            user_id=user_id,
            senders=account.authorized_senders,
            now_ms=now_ms,
        )
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in ("unique", "primary_key"):
            raise ConflictError("Messaging account principal is already configured.") from exception
        if constraint_type in ("foreign_key", "check"):
            raise ValidationError(
                f"Messaging account data violates {detail or constraint_type}.",
            ) from exception
        raise StateError("Messaging account could not be created.") from exception
    created = sync_read_messaging_account(conn, user_id, account_id)
    if created is None:
        raise StateError("Messaging account could not be reloaded after creation.")
    return created


def sync_update_messaging_account(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
    expected_revision: int,
    account: MessagingAccountUpdate,
    credential_ciphertext: str | None,
    credential_fingerprint: str | None,
    model_settings_json: str,
) -> JSONDict | None:
    now_ms = epoch_ms()
    try:
        updated = conn.execute(
            """
            UPDATE messaging_accounts
            SET label = ?,
                principal_label = ?, parent_principal_id = ?,
                application_principal_id = ?,
                credential_ciphertext = COALESCE(?, credential_ciphertext),
                credential_fingerprint = COALESCE(?, credential_fingerprint),
                model_settings_json = ?, locale = ?, lifecycle_state = ?,
                plaintext_secret_replies_enabled = ?,
                accept_messages_from_anyone = ?, revision = revision + 1,
                health_code = NULL, health_checked_at_ms = NULL, updated_at_ms = ?
            WHERE user_id = ? AND account_id = ? AND revision = ?
              AND lifecycle_state != 'deleting'
            """,
            (
                account.label,
                account.principal_label,
                account.parent_principal_id,
                account.application_principal_id,
                credential_ciphertext,
                credential_fingerprint,
                model_settings_json,
                account.locale,
                account.lifecycle_state,
                1 if account.plaintext_secret_replies_enabled else 0,
                1 if account.accept_messages_from_anyone else 0,
                now_ms,
                user_id,
                account_id,
                expected_revision,
            ),
        ).rowcount
        if updated != 1:
            if sync_read_messaging_account(conn, user_id, account_id) is None:
                return None
            raise ConflictError("Messaging account changed before this update was applied.")
        if account.lifecycle_state == "disabled":
            _fence_disabled_account(conn, account_id=account_id, user_id=user_id, now_ms=now_ms)
        if not account.accept_messages_from_anyone:
            _fence_removed_senders(
                conn,
                account_id=account_id,
                user_id=user_id,
                senders=account.authorized_senders,
                now_ms=now_ms,
            )
        conn.execute(
            "DELETE FROM messaging_authorized_senders WHERE account_id = ? AND user_id = ?",
            (account_id, user_id),
        )
        _insert_senders(
            conn,
            account_id=account_id,
            user_id=user_id,
            senders=account.authorized_senders,
            now_ms=now_ms,
        )
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in ("unique", "primary_key"):
            raise ConflictError("Messaging authorized senders must be unique.") from exception
        raise ValidationError(
            f"Messaging account update violates {detail or constraint_type}.",
        ) from exception
    result = sync_read_messaging_account(conn, user_id, account_id)
    if result is None:
        raise StateError("Messaging account disappeared after update.")
    return result


def sync_set_messaging_account_lifecycle_state(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
    expected_revision: int,
    lifecycle_state: MessagingAccountLifecycleState,
) -> JSONDict | None:
    now_ms = epoch_ms()
    updated = conn.execute(
        """
        UPDATE messaging_accounts
        SET lifecycle_state = ?, revision = revision + 1,
            health_code = NULL, health_checked_at_ms = NULL, updated_at_ms = ?
        WHERE user_id = ? AND account_id = ? AND revision = ?
          AND lifecycle_state != 'deleting'
        """,
        (lifecycle_state, now_ms, user_id, account_id, expected_revision),
    ).rowcount
    if updated != 1:
        if sync_read_messaging_account(conn, user_id, account_id) is None:
            return None
        raise ConflictError("Messaging account changed before this update was applied.")
    if lifecycle_state == "disabled":
        _fence_disabled_account(conn, account_id=account_id, user_id=user_id, now_ms=now_ms)
    result = sync_read_messaging_account(conn, user_id, account_id)
    if result is None:
        raise StateError("Messaging account disappeared after lifecycle update.")
    return result

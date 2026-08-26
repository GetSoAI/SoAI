"""SoAI - Messaging account reconciliation persistence [backend/database/repositories/users/messaging_account_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.messaging.account_models import MessagingAccountReconciliationResult
from core.timing.epoch import epoch_ms
from database.repositories.users.messaging_account_reads import sync_read_messaging_account
from database.repositories.users.messaging_health_notifications import (
    sync_create_messaging_health_notification,
)

if TYPE_CHECKING:
    from core.messaging.callback_contracts import MessagingCallbackOwnershipState

__all__ = ("sync_record_messaging_account_reconciliation",)


def sync_record_messaging_account_reconciliation(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
    expected_revision: int,
    lifecycle_generation: int,
    healthy: bool | None,
    callback_fingerprint: str | None,
    ownership_state: MessagingCallbackOwnershipState,
    health_code: str | None,
    max_notifications_per_user: int,
) -> MessagingAccountReconciliationResult | None:
    before = sync_read_messaging_account(conn, user_id, account_id)
    if (
        before is None
        or before.get("revision") != expected_revision
        or before.get("lifecycle_generation") != lifecycle_generation
        or before.get("lifecycle_state") == "deleting"
    ):
        return None
    now_ms = epoch_ms()
    updated = conn.execute(
        """
        UPDATE messaging_accounts
        SET lifecycle_state = CASE
                WHEN lifecycle_state = 'disabled' THEN 'disabled'
                WHEN ? IS NULL THEN lifecycle_state
                WHEN ? = 1 THEN 'enabled'
                ELSE 'degraded'
            END,
            installed_callback_fingerprint = ?, callback_ownership_state = ?,
            health_code = ?, health_checked_at_ms = ?, updated_at_ms = ?
        WHERE user_id = ? AND account_id = ? AND revision = ?
          AND lifecycle_generation = ? AND lifecycle_state != 'deleting'
        """,
        (
            None if healthy is None else 1 if healthy else 0,
            None if healthy is None else 1 if healthy else 0,
            callback_fingerprint,
            ownership_state,
            health_code,
            now_ms,
            now_ms,
            user_id,
            account_id,
            expected_revision,
            lifecycle_generation,
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Messaging account reconciliation write lost its fenced target.")
    after = sync_read_messaging_account(conn, user_id, account_id)
    if after is None:
        raise StateError("Messaging account reconciliation target disappeared.")
    before_state = before.get("lifecycle_state")
    after_state = after.get("lifecycle_state")
    notification_created = False
    if before_state == "enabled" and after_state == "degraded":
        notification_created = sync_create_messaging_health_notification(
            conn,
            account=after,
            recovered=False,
            created_at_ms=now_ms,
            max_per_user=max_notifications_per_user,
        )
    elif before_state == "degraded" and after_state == "enabled":
        notification_created = sync_create_messaging_health_notification(
            conn,
            account=after,
            recovered=True,
            created_at_ms=now_ms,
            max_per_user=max_notifications_per_user,
        )
    return MessagingAccountReconciliationResult(
        before=before,
        after=after,
        notification_created=notification_created,
    )

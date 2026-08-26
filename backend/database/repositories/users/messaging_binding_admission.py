"""SoAI - Messaging account and thread admission [backend/database/repositories/users/messaging_binding_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from database.repositories.users.conversation_creation import sync_create_conversation
from database.repositories.users.conversation_versioning import NEXT_LAST_MODIFIED_SQL

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = (
    "ensure_messaging_account_capacity",
    "is_messaging_sender_authorized",
    "read_messaging_admission_account",
    "resolve_messaging_bound_conversation",
)

MAX_ACCOUNT_ACTIVE_INPUTS = 1_000


def read_messaging_admission_account(
    conn: sqlite3.Connection,
    account_id: str,
    platform: str,
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT account_id, user_id, platform, label, principal_id, model_settings_json,
               lifecycle_state, lifecycle_generation, principal_label, locale,
               plaintext_secret_replies_enabled, accept_messages_from_anyone
        FROM messaging_accounts
        WHERE account_id = ? AND platform = ?
        """,
        (account_id, platform),
    ).fetchone()
    if not isinstance(row, sqlite3.Row):
        raise ConflictError("Messaging account is unavailable.")
    if row[6] not in ("enabled", "degraded"):
        raise ConflictError("Messaging account admission is closed.")
    return row


def is_messaging_sender_authorized(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    sender_id: str,
    accept_messages_from_anyone: bool,
) -> bool:
    if accept_messages_from_anyone:
        return True
    return (
        conn.execute(
            """
            SELECT 1
            FROM messaging_authorized_senders
            WHERE account_id = ? AND user_id = ? AND sender_id = ?
            """,
            (account_id, user_id, sender_id),
        ).fetchone()
        is not None
    )


def ensure_messaging_account_capacity(conn: sqlite3.Connection, account_id: str) -> None:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM webui_conversation_inputs AS input
        JOIN messaging_ingress_events AS ingress
          ON ingress.ingress_id = input.messaging_ingress_id
        WHERE ingress.account_id = ?
          AND input.state IN ('pending', 'materializing', 'running', 'input_required')
        """,
        (account_id,),
    ).fetchone()
    if row is None or not isinstance(row[0], int):
        raise StateError("Messaging input capacity could not be measured.")
    if row[0] >= MAX_ACCOUNT_ACTIVE_INPUTS:
        raise ConflictError("Messaging account input capacity is exhausted.")


def resolve_messaging_bound_conversation(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    account_label: str,
    model_settings: JSONDict,
    event: NormalizedMessagingEvent,
    title: str,
    conv_id: str,
    accepted_at_ms: int,
) -> tuple[str, int, int]:
    binding = conn.execute(
        """
        SELECT binding.conv_id, binding.binding_generation,
               conversation.is_messaging, conversation.messaging_platform,
               conversation.messaging_account_snapshot_id, binding.pending_reset_state
        FROM messaging_thread_bindings
        AS binding
        JOIN webui_conversations AS conversation
          ON conversation.id = binding.conv_id AND conversation.user_id = binding.user_id
        WHERE binding.account_id = ? AND binding.user_id = ?
          AND binding.remote_thread_type = ? AND binding.remote_thread_key = ?
        """,
        (account_id, user_id, event.remote_thread_type, event.remote_thread_key),
    ).fetchone()
    if binding is None:
        conversation = sync_create_conversation(
            conn,
            user_id,
            title,
            model_settings,
            False,
            conv_id,
            messaging_platform=event.platform,
            messaging_account_label=account_label,
            messaging_account_snapshot_id=account_id,
        )
        input_generation = conversation.get("input_generation")
        if not isinstance(input_generation, int):
            raise StateError("Messaging conversation input generation is invalid.")
        conn.execute(
            """
            INSERT INTO messaging_thread_bindings (
                account_id, user_id, remote_thread_type, remote_thread_key,
                conv_id, binding_generation, created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                account_id,
                user_id,
                event.remote_thread_type,
                event.remote_thread_key,
                conv_id,
                accepted_at_ms,
                accepted_at_ms,
            ),
        )
        return (conv_id, 0, input_generation)
    if binding[5] == "accepted":
        raise ConflictError("Messaging conversation reset is pending.")
    (
        bound_conv_id,
        binding_generation,
        is_messaging,
        platform,
        snapshot_id,
        _pending_reset_state,
    ) = binding
    if not isinstance(bound_conv_id, str) or not isinstance(binding_generation, int):
        raise StateError("Messaging thread binding is invalid.")
    if is_messaging != 1 or platform != event.platform or snapshot_id != account_id:
        raise ConflictError("Messaging thread binding ownership is invalid.")
    conn.execute(
        f"""
        UPDATE webui_conversations
        SET is_archived = 0,
            last_modified_at_ms = CASE
                WHEN is_archived = 1 THEN {NEXT_LAST_MODIFIED_SQL}
                ELSE last_modified_at_ms
            END
        WHERE id = ? AND user_id = ? AND is_messaging = 1
        """,
        (accepted_at_ms, accepted_at_ms, bound_conv_id, user_id),
    )
    conversation = conn.execute(
        "SELECT input_generation FROM webui_conversations WHERE id = ? AND user_id = ?",
        (bound_conv_id, user_id),
    ).fetchone()
    if conversation is None or not isinstance(conversation[0], int):
        raise ConflictError("Messaging thread conversation is unavailable.")
    return (bound_conv_id, binding_generation, conversation[0])

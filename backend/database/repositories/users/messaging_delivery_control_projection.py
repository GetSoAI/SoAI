"""SoAI - Completed conversation control delivery projection [backend/database/repositories/users/messaging_delivery_control_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.openai.content_text_rendering import render_openai_content_text
from database.core.json_codec import safe_json_deserialize
from database.repositories.users.messaging_delivery_insertion import (
    MessagingDeliveryIntent,
    sync_insert_messaging_delivery_intent,
)

if TYPE_CHECKING:
    from core.events.types_conversation_durable import ConversationControlCompletedEvent
    from core.types.json import JSONDict

__all__ = ("sync_project_control_messaging_delivery",)


def _read_existing_projection(
    conn: sqlite3.Connection,
    event: ConversationControlCompletedEvent,
) -> JSONDict | None:
    row = conn.execute(
        "SELECT delivery_id, state, source_message_id, purpose FROM messaging_deliveries WHERE source_event_id = ?",
        (event.event_id,),
    ).fetchone()
    if row is None:
        return None
    if row[2] != event.source_message_id or row[3] != "control":
        raise StateError("Messaging control delivery event identity collided.")
    return {"delivery_id": row[0], "state": row[1]}


def sync_project_control_messaging_delivery(
    conn: sqlite3.Connection,
    event: ConversationControlCompletedEvent,
) -> JSONDict | None:
    existing = _read_existing_projection(conn, event)
    if existing is not None:
        return existing
    row = conn.execute(
        """
        SELECT ingress.account_id, ingress.user_id, ingress.platform,
               ingress.remote_thread_type, ingress.remote_thread_key, ingress.sender_id,
               ingress.account_generation, ingress.binding_generation,
               account.lifecycle_state, account.lifecycle_generation,
               binding.conv_id, binding.binding_generation,
               CASE WHEN account.accept_messages_from_anyone = 1
                         OR sender.sender_id IS NOT NULL THEN 1 ELSE 0 END,
               message.content, message.finalized_at_ms
        FROM messaging_ingress_events AS ingress
        JOIN messaging_accounts AS account
          ON account.account_id = ingress.account_id AND account.user_id = ingress.user_id
        LEFT JOIN messaging_thread_bindings AS binding
          ON binding.account_id = ingress.account_id AND binding.user_id = ingress.user_id
         AND binding.remote_thread_type = ingress.remote_thread_type
         AND binding.remote_thread_key = ingress.remote_thread_key
        LEFT JOIN messaging_authorized_senders AS sender
          ON sender.account_id = ingress.account_id AND sender.user_id = ingress.user_id
         AND sender.sender_id = ingress.sender_id
        JOIN webui_messages AS message
          ON message.id = ? AND message.conv_id = ?
         AND message.role = 'assistant' AND message.message_type = 'control'
        WHERE ingress.ingress_id = ? AND ingress.user_id = ?
          AND ingress.result_conv_id = ? AND ingress.outcome = 'accepted'
        LIMIT 1
        """,
        (
            event.source_message_id,
            event.conv_id,
            event.control_id,
            event.user_id,
            event.target_conv_id,
        ),
    ).fetchone()
    if row is None:
        raise StateError("Messaging control delivery source is unavailable.")
    if not all(isinstance(row[index], str) for index in (0, 2, 3, 4, 5)):
        raise StateError("Messaging control delivery target is invalid.")
    if not isinstance(row[1], int) or row[1] != event.user_id:
        raise StateError("Messaging control delivery owner is invalid.")
    if not isinstance(row[6], int) or not isinstance(row[7], int):
        raise StateError("Messaging control delivery generation is invalid.")
    state = "pending"
    failure_code: str | None = None
    if row[8] not in ("enabled", "degraded"):
        state, failure_code = ("skipped", "messaging_account_delivery_closed")
    elif row[9] != row[6]:
        state, failure_code = ("skipped", "messaging_account_generation_changed")
    elif row[10] != event.target_conv_id or row[11] != row[7]:
        state, failure_code = ("skipped", "messaging_binding_generation_changed")
    elif row[12] != 1:
        state, failure_code = ("skipped", "messaging_sender_revoked")
    if not isinstance(row[13], str) or not isinstance(row[14], int):
        raise StateError("Messaging control response is not finalized.")
    content = render_openai_content_text(safe_json_deserialize(row[13]))
    if not content:
        raise StateError("Messaging control response is empty.")
    return sync_insert_messaging_delivery_intent(
        conn,
        MessagingDeliveryIntent(
            source_event_id=event.event_id,
            account_id=row[0],
            user_id=row[1],
            platform=row[2],
            remote_thread_type=row[3],
            remote_thread_key=row[4],
            originating_sender_id=row[5],
            account_generation=row[6],
            binding_generation=row[7],
            source_input_id=None,
            source_message_id=event.source_message_id,
            purpose="control",
            content_text=content,
            initial_state=state,
            failure_code=failure_code,
            created_at_ms=int(event.timestamp * 1000),
        ),
    )

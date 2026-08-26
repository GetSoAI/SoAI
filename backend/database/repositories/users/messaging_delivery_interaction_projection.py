"""SoAI - Interaction-required Messaging delivery projection [backend/database/repositories/users/messaging_delivery_interaction_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.messaging.interaction_focus_url import build_messaging_interaction_focus_url
from core.messaging.interaction_prompt import render_messaging_interaction_prompt
from core.types.json_value import coerce_json_dict
from database.core.json_codec import safe_json_deserialize
from database.repositories.users.messaging_delivery_insertion import (
    MessagingDeliveryIntent,
    sync_insert_messaging_delivery_intent,
)

if TYPE_CHECKING:
    from core.events.types_conversation_durable import ConversationInteractionRequiredEvent
    from core.types.json import JSONDict

__all__ = ("sync_project_interaction_messaging_delivery",)


def _read_existing_projection(
    conn: sqlite3.Connection,
    event: ConversationInteractionRequiredEvent,
) -> JSONDict | None:
    row = conn.execute(
        """
        SELECT delivery_id, state, source_input_id, purpose
        FROM messaging_deliveries WHERE source_event_id = ?
        """,
        (event.event_id,),
    ).fetchone()
    if row is None:
        return None
    if row[2] != event.input_id or row[3] != "interaction":
        raise StateError("Messaging interaction delivery event identity collided.")
    return {"delivery_id": row[0], "state": row[1]}


def sync_project_interaction_messaging_delivery(
    conn: sqlite3.Connection,
    event: ConversationInteractionRequiredEvent,
    public_origin: str | None,
) -> JSONDict | None:
    existing = _read_existing_projection(conn, event)
    if existing is not None:
        return existing
    row = conn.execute(
        """
        SELECT route.account_id, route.user_id, account.platform,
               route.remote_thread_type, route.remote_thread_key,
               route.originating_sender_id, route.account_generation,
               route.binding_generation, binding.binding_generation,
               account.lifecycle_state, account.lifecycle_generation,
               account.locale, binding.conv_id,
               CASE WHEN account.accept_messages_from_anyone = 1
                         OR sender.sender_id IS NOT NULL THEN 1 ELSE 0 END,
               task.metadata, route.state, route.input_id, route.interaction_type,
               route.reply_token_hash, route.focus_nonce_hash
        FROM messaging_interaction_routes AS route
        JOIN messaging_accounts AS account
          ON account.account_id = route.account_id AND account.user_id = route.user_id
        LEFT JOIN messaging_thread_bindings AS binding
          ON binding.account_id = route.account_id AND binding.user_id = route.user_id
         AND binding.remote_thread_type = route.remote_thread_type
         AND binding.remote_thread_key = route.remote_thread_key
        LEFT JOIN messaging_authorized_senders AS sender
          ON sender.account_id = route.account_id AND sender.user_id = route.user_id
         AND sender.sender_id = route.originating_sender_id
        JOIN unified_tasks AS task ON task.task_id = route.task_id
        WHERE route.route_id = ? AND route.task_id = ? AND route.conv_id = ?
          AND route.user_id = ?
        LIMIT 1
        """,
        (event.route_id, event.task_id, event.conv_id, event.user_id),
    ).fetchone()
    if row is None:
        raise StateError("Messaging interaction delivery source is unavailable.")
    if not all(isinstance(row[index], str) and row[index] for index in (0, 2, 3, 4, 5, 11)):
        raise StateError("Messaging interaction delivery target is invalid.")
    if not all(isinstance(row[index], int) for index in (1, 6, 7, 8, 10)):
        raise StateError("Messaging interaction delivery generation is invalid.")
    if row[1] != event.user_id or row[16] != event.input_id or row[17] != event.interaction_type:
        raise StateError("Messaging interaction delivery identity is stale.")
    if row[18] != hashlib.sha256(event.reply_token.casefold().encode()).hexdigest():
        raise StateError("Messaging interaction reply token is stale.")
    if row[19] != hashlib.sha256(event.focus_nonce.encode()).hexdigest():
        raise StateError("Messaging interaction focus nonce is stale.")
    state = "pending"
    failure_code: str | None = None
    if row[15] != "pending":
        state, failure_code = ("skipped", "messaging_interaction_closed")
    elif row[9] not in {"enabled", "degraded"}:
        state, failure_code = ("skipped", "messaging_account_delivery_closed")
    elif row[10] != row[6]:
        state, failure_code = ("skipped", "messaging_account_generation_changed")
    elif row[8] != row[7] or row[12] != event.conv_id:
        state, failure_code = ("skipped", "messaging_binding_generation_changed")
    elif row[13] != 1:
        state, failure_code = ("skipped", "messaging_sender_revoked")
    elif not isinstance(public_origin, str) or not public_origin.strip():
        state, failure_code = ("skipped", "messaging_public_origin_unavailable")
    task_metadata = coerce_json_dict(
        safe_json_deserialize(row[14]) if isinstance(row[14], str) else None,
    )
    if task_metadata is None:
        raise StateError("Messaging interaction task metadata is invalid.")
    content = ""
    if state == "pending":
        if public_origin is None:
            raise StateError("Messaging interaction public origin state is invalid.")
        focus_url = build_messaging_interaction_focus_url(
            public_origin=public_origin,
            conv_id=event.conv_id,
            focus_nonce=event.focus_nonce,
        )
        content = render_messaging_interaction_prompt(
            locale=row[11],
            interaction_type=event.interaction_type,
            task_metadata=task_metadata,
            reply_token=event.reply_token,
            focus_url=focus_url,
        )
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
            source_input_id=event.input_id,
            source_message_id=None,
            purpose="interaction",
            content_text=content,
            initial_state=state,
            failure_code=failure_code,
            created_at_ms=int(event.timestamp * 1000),
        ),
    )

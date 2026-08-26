"""SoAI - Terminal input to Messaging delivery projection [backend/database/repositories/users/messaging_delivery_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.messaging.response_catalog import resolve_messaging_response_text
from core.openai.content_text_rendering import render_openai_content_text
from database.core.json_codec import safe_json_deserialize
from database.repositories.users.messaging_delivery_insertion import (
    MessagingDeliveryIntent,
    sync_insert_messaging_delivery_intent,
)

if TYPE_CHECKING:
    from core.events.types_conversation_durable import ConversationInputTerminalEvent
    from core.types.json import JSONDict

__all__ = ("sync_project_terminal_messaging_delivery",)


def _delivery_content(row: sqlite3.Row, terminal_state: str) -> str:
    locale = row[12]
    if not isinstance(locale, str):
        raise StateError("Messaging delivery locale is invalid.")
    if terminal_state == "completed":
        message_content = row[17]
        finalized_at_ms = row[18]
        if (
            isinstance(message_content, str)
            and message_content
            and isinstance(finalized_at_ms, int)
        ):
            rendered = render_openai_content_text(safe_json_deserialize(message_content))
            if rendered:
                return rendered
        return resolve_messaging_response_text(locale, "completed_empty")
    return resolve_messaging_response_text(locale, terminal_state)


def _projection_state(row: sqlite3.Row) -> tuple[str, str | None]:
    if row[10] not in ("enabled", "degraded"):
        return ("skipped", "messaging_account_delivery_closed")
    if row[11] != row[14]:
        return ("skipped", "messaging_account_generation_changed")
    if row[13] is None or row[13] != row[15]:
        return ("skipped", "messaging_binding_generation_changed")
    if row[16] != 1:
        return ("skipped", "messaging_sender_revoked")
    return ("pending", None)


def _read_projection_row(
    conn: sqlite3.Connection,
    event: ConversationInputTerminalEvent,
) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT input.transport_origin, input.state, input.terminal_code,
               ingress.account_id, ingress.user_id, ingress.platform,
               ingress.remote_thread_type, ingress.remote_thread_key, ingress.sender_id,
               binding.conv_id, account.lifecycle_state, account.lifecycle_generation,
               account.locale, binding.binding_generation,
               json_extract(input.source_metadata_json, '$.account_generation'),
               json_extract(input.source_metadata_json, '$.binding_generation'),
               CASE WHEN account.accept_messages_from_anyone = 1
                         OR sender.sender_id IS NOT NULL THEN 1 ELSE 0 END,
               message.content, message.finalized_at_ms
        FROM webui_conversation_inputs AS input
        LEFT JOIN messaging_ingress_events AS ingress
          ON ingress.ingress_id = input.messaging_ingress_id
        LEFT JOIN messaging_accounts AS account
          ON account.account_id = ingress.account_id AND account.user_id = ingress.user_id
        LEFT JOIN messaging_thread_bindings AS binding
          ON binding.account_id = ingress.account_id AND binding.user_id = ingress.user_id
         AND binding.remote_thread_type = ingress.remote_thread_type
         AND binding.remote_thread_key = ingress.remote_thread_key
        LEFT JOIN messaging_authorized_senders AS sender
          ON sender.account_id = ingress.account_id AND sender.user_id = ingress.user_id
         AND sender.sender_id = ingress.sender_id
        LEFT JOIN webui_messages AS message
          ON message.id = ? AND message.conv_id = input.conv_id AND message.role = 'assistant'
        WHERE input.input_id = ? AND input.user_id = ? AND input.conv_id = ?
        LIMIT 1
        """,
        (event.source_message_id, event.input_id, event.user_id, event.conv_id),
    ).fetchone()
    if row is None:
        return None
    if not isinstance(row, sqlite3.Row):
        raise StateError("Messaging delivery projection row is invalid.")
    return row


def _read_existing_projection(
    conn: sqlite3.Connection,
    event_id: str,
) -> JSONDict | None:
    row = conn.execute(
        """
        SELECT delivery_id, state, source_input_id, source_message_id
        FROM messaging_deliveries WHERE source_event_id = ?
        """,
        (event_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "delivery_id": row[0],
        "state": row[1],
        "source_input_id": row[2],
        "source_message_id": row[3],
    }


def sync_project_terminal_messaging_delivery(
    conn: sqlite3.Connection,
    event: ConversationInputTerminalEvent,
) -> JSONDict | None:
    existing = _read_existing_projection(conn, event.event_id)
    if existing is not None:
        if (
            existing["source_input_id"] != event.input_id
            or existing["source_message_id"] != event.source_message_id
        ):
            raise StateError("Messaging delivery event identity collided.")
        return {
            "delivery_id": existing["delivery_id"],
            "state": existing["state"],
        }
    row = _read_projection_row(conn, event)
    if row is None or row[0] == "chat" or row[3] is None:
        return None
    if row[1] != event.terminal_state or row[2] != event.terminal_code:
        raise StateError("Conversation input terminal event no longer matches persistence.")
    if event.terminal_state not in {"completed", "failed", "cancelled", "effect_unknown"}:
        raise StateError("Messaging terminal delivery state is invalid.")
    if not all(isinstance(row[index], str) for index in (3, 5, 6, 7, 8)):
        raise StateError("Messaging delivery target is invalid.")
    if not isinstance(row[4], int) or not isinstance(row[11], int):
        raise StateError("Messaging delivery ownership is invalid.")
    if row[4] != event.user_id or row[9] != event.conv_id:
        raise StateError("Messaging delivery binding no longer matches the terminal input.")
    if not isinstance(row[14], int) or not isinstance(row[15], int):
        raise StateError("Messaging delivery accepted generations are invalid.")
    if event.source_message_id is not None and not isinstance(row[18], int):
        raise StateError("Messaging delivery source assistant is not finalized.")
    if event.terminal_state == "completed" and event.source_message_id is None:
        raise StateError("Completed Messaging delivery is missing its assistant message.")
    state, failure_code = _projection_state(row)
    content = _delivery_content(row, event.terminal_state)
    return sync_insert_messaging_delivery_intent(
        conn,
        MessagingDeliveryIntent(
            source_event_id=event.event_id,
            account_id=row[3],
            user_id=row[4],
            platform=row[5],
            remote_thread_type=row[6],
            remote_thread_key=row[7],
            originating_sender_id=row[8],
            account_generation=row[14],
            binding_generation=row[15],
            source_input_id=event.input_id,
            source_message_id=event.source_message_id,
            purpose="assistant",
            content_text=content,
            initial_state=state,
            failure_code=failure_code,
            created_at_ms=int(event.timestamp * 1000),
        ),
    )

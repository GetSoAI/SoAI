"""SoAI - Atomic Messaging control admission [backend/database/repositories/users/messaging_control_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.messaging.response_catalog import resolve_messaging_response_text
from database.repositories.users.conversation_control_events import (
    sync_ensure_conversation_control_completed_event,
)
from database.repositories.users.conversation_control_messages import (
    sync_append_conversation_control_exchange,
)
from database.repositories.users.conversation_input_active_state_reads import (
    sync_read_active_conversation_input_summary,
)
from database.repositories.users.conversation_input_sync_cancel import (
    sync_cancel_conversation_input,
)
from database.repositories.users.messaging_binding_admission import (
    resolve_messaging_bound_conversation,
)
from database.repositories.users.messaging_ingress_records import (
    insert_messaging_ingress_record,
)
from database.repositories.users.messaging_reset_operations import (
    sync_accept_messaging_reset,
)

if TYPE_CHECKING:
    from core.messaging.control_commands import MessagingControlCommand
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = ("sync_admit_messaging_control",)


def _read_bound_conversation(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    event: NormalizedMessagingEvent,
) -> str | None:
    row = conn.execute(
        """
        SELECT conv_id, pending_reset_state
        FROM messaging_thread_bindings
        WHERE account_id = ? AND user_id = ?
          AND remote_thread_type = ? AND remote_thread_key = ?
        """,
        (account_id, user_id, event.remote_thread_type, event.remote_thread_key),
    ).fetchone()
    if row is None:
        return None
    if row[1] == "accepted":
        raise StateError("Messaging conversation reset is pending.")
    if not isinstance(row[0], str):
        raise StateError("Messaging conversation binding is invalid.")
    return row[0]


def _status_response_key(conn: sqlite3.Connection, conv_id: str, user_id: int) -> str:
    summary = sync_read_active_conversation_input_summary(conn, conv_id, user_id)
    if summary.head_state is None:
        return "status_idle"
    if summary.head_state == "input_required":
        return "status_input_required"
    if summary.head_state in ("materializing", "running"):
        return "status_running"
    return "status_pending"


def _cancel_sender_input(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    sender_id: str,
) -> tuple[str | None, bool]:
    row = conn.execute(
        """
        SELECT input_id, state, materialized_message_id
        FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ? AND transport_origin = 'messaging'
          AND json_extract(source_metadata_json, '$.sender_id') = ?
          AND state IN ('pending', 'materializing', 'running', 'input_required')
        ORDER BY accepted_at_ms ASC, id ASC LIMIT 1
        """,
        (conv_id, user_id, sender_id),
    ).fetchone()
    if row is None:
        return (None, False)
    input_id, state, materialized_message_id = row
    if not isinstance(input_id, str):
        raise StateError("Cancellable Messaging input identity is invalid.")
    if state == "pending" or (state == "materializing" and materialized_message_id is None):
        sync_cancel_conversation_input(conn, conv_id, user_id, input_id)
        return (None, True)
    return (input_id, True)


def _resolve_control_response(
    conn: sqlite3.Connection,
    *,
    command: MessagingControlCommand,
    conv_id: str,
    user_id: int,
    sender_id: str,
    locale: str,
) -> tuple[str, str | None]:
    if command == "help":
        return (resolve_messaging_response_text(locale, "help"), None)
    if command == "status":
        return (
            resolve_messaging_response_text(
                locale,
                _status_response_key(conn, conv_id, user_id),
            ),
            None,
        )
    cancellation_input_id, cancellation_requested = _cancel_sender_input(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        sender_id=sender_id,
    )
    response_key = "cancel_requested" if cancellation_requested else "cancel_none"
    return (resolve_messaging_response_text(locale, response_key), cancellation_input_id)


def sync_admit_messaging_control(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    account_label: str,
    account_generation: int,
    locale: str,
    model_settings: JSONDict,
    ingress_id: str,
    conversation_id: str,
    command: MessagingControlCommand,
    event: NormalizedMessagingEvent,
    content_fingerprint: str,
    title: str,
    accepted_at_ms: int,
) -> JSONDict:
    sender_id = event.sender_id
    if sender_id is None:
        raise StateError("Messaging control sender is unavailable.")
    existing_conv_id = _read_bound_conversation(
        conn,
        account_id=account_id,
        user_id=user_id,
        event=event,
    )
    insert_messaging_ingress_record(
        conn,
        ingress_id=ingress_id,
        account_id=account_id,
        user_id=user_id,
        event=event,
        content_fingerprint=content_fingerprint,
        classification="control",
        outcome="accepted",
        sender_id=sender_id,
        diagnostic_code=None,
        accepted_at_ms=accepted_at_ms,
    )
    conv_id, binding_generation, _revision = resolve_messaging_bound_conversation(
        conn,
        account_id=account_id,
        user_id=user_id,
        account_label=account_label,
        model_settings=model_settings,
        event=event,
        title=title,
        conv_id=conversation_id,
        accepted_at_ms=accepted_at_ms,
    )
    if command == "new" and existing_conv_id is not None:
        return sync_accept_messaging_reset(
            conn,
            account_id=account_id,
            user_id=user_id,
            account_generation=account_generation,
            ingress_id=ingress_id,
            event=event,
            old_conv_id=conv_id,
            accepted_at_ms=accepted_at_ms,
        )
    if command == "new":
        response_text = resolve_messaging_response_text(locale, "new_completed")
        cancellation_input_id = None
    else:
        response_text, cancellation_input_id = _resolve_control_response(
            conn,
            command=command,
            conv_id=conv_id,
            user_id=user_id,
            sender_id=sender_id,
            locale=locale,
        )
    exchange = sync_append_conversation_control_exchange(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        command_text=f"/{command}",
        response_text=response_text,
        completed_at_ms=accepted_at_ms,
    )
    source_message_id = exchange.get("source_message_id")
    if not isinstance(source_message_id, int):
        raise StateError("Messaging control response identity is invalid.")
    conn.execute(
        """
        UPDATE messaging_ingress_events
        SET linked_control_id = ?, linked_input_id = ?, result_conv_id = ?,
            account_generation = ?, binding_generation = ?, diagnostic_code = ?
        WHERE ingress_id = ?
        """,
        (
            ingress_id,
            cancellation_input_id,
            conv_id,
            account_generation,
            binding_generation,
            "cancel_pending" if cancellation_input_id is not None else None,
            ingress_id,
        ),
    )
    sync_ensure_conversation_control_completed_event(
        conn,
        control_id=ingress_id,
        user_id=user_id,
        conv_id=conv_id,
        target_conv_id=conv_id,
        source_message_id=source_message_id,
        created_at_ms=accepted_at_ms,
    )
    return {
        "status": "accepted",
        "outcome": "accepted",
        "classification": "control",
        "ingress_id": ingress_id,
        "control_id": ingress_id,
        "conv_id": conv_id,
        "user_id": user_id,
        "conversation_created": existing_conv_id is None,
        "cancellation_input_id": cancellation_input_id,
        "message_count": exchange.get("message_count"),
        "last_modified_at_ms": exchange.get("last_modified_at_ms"),
    }

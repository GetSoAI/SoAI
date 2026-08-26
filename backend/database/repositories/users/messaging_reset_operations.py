"""SoAI - Durable Messaging conversation reset operations [backend/database/repositories/users/messaging_reset_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from core.messaging.response_catalog import resolve_messaging_response_text
from core.serialization.json_parsing import parse_json_dict
from core.timing.epoch import epoch_ms
from database.repositories.users.conversation_control_events import (
    sync_ensure_conversation_control_completed_event,
)
from database.repositories.users.conversation_control_messages import (
    sync_append_conversation_control_exchange,
)
from database.repositories.users.conversation_creation import sync_create_conversation
from database.repositories.users.conversation_input_sync_cancel import (
    sync_cancel_conversation_input,
)

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = (
    "sync_accept_messaging_reset",
    "sync_complete_pending_messaging_resets",
)


def _cancel_safe_reset_inputs(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> str | None:
    rows = conn.execute(
        """
        SELECT input_id, state, materialized_message_id
        FROM webui_conversation_inputs
        WHERE conv_id = ? AND user_id = ?
          AND state IN ('pending', 'materializing', 'running', 'input_required')
        ORDER BY accepted_at_ms ASC, id ASC
        """,
        (conv_id, user_id),
    ).fetchall()
    active_input_id: str | None = None
    for input_id, state, materialized_message_id in rows:
        if not isinstance(input_id, str):
            raise StateError("Messaging reset input identity is invalid.")
        if state == "pending" or (state == "materializing" and materialized_message_id is None):
            sync_cancel_conversation_input(conn, conv_id, user_id, input_id)
        elif active_input_id is None:
            active_input_id = input_id
    return active_input_id


def sync_accept_messaging_reset(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    user_id: int,
    account_generation: int,
    ingress_id: str,
    event: NormalizedMessagingEvent,
    old_conv_id: str,
    accepted_at_ms: int,
) -> JSONDict:
    updated = conn.execute(
        """
        UPDATE messaging_thread_bindings
        SET pending_reset_control_id = ?, pending_reset_state = 'accepted',
            binding_generation = binding_generation + 1, updated_at_ms = ?
        WHERE account_id = ? AND user_id = ?
          AND remote_thread_type = ? AND remote_thread_key = ?
          AND conv_id = ? AND pending_reset_state IS NULL
        RETURNING binding_generation
        """,
        (
            ingress_id,
            accepted_at_ms,
            account_id,
            user_id,
            event.remote_thread_type,
            event.remote_thread_key,
            old_conv_id,
        ),
    ).fetchone()
    if updated is None or not isinstance(updated[0], int):
        raise ConflictError("Messaging conversation reset is already pending.")
    binding_generation = updated[0]
    cancellation_input_id = _cancel_safe_reset_inputs(
        conn,
        conv_id=old_conv_id,
        user_id=user_id,
    )
    conn.execute(
        """
        UPDATE messaging_ingress_events
        SET linked_control_id = ?, old_conv_id = ?, result_conv_id = NULL,
            account_generation = ?, binding_generation = ?, diagnostic_code = 'reset_pending'
        WHERE ingress_id = ?
        """,
        (
            ingress_id,
            old_conv_id,
            account_generation,
            binding_generation,
            ingress_id,
        ),
    )
    return {
        "status": "reset_pending",
        "outcome": "accepted",
        "ingress_id": ingress_id,
        "control_id": ingress_id,
        "conv_id": old_conv_id,
        "old_conv_id": old_conv_id,
        "user_id": user_id,
        "binding_generation": binding_generation,
        "cancellation_input_id": cancellation_input_id,
        "conversation_created": False,
    }


def _replacement_conversation_id(control_id: str) -> str:
    digest = hashlib.sha256(f"{control_id}:conversation".encode()).hexdigest()[:24]
    return f"conv_{digest}"


def _complete_reset_row(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    completed_at_ms: int,
) -> JSONDict:
    account_id, user_id, thread_type, thread_key, old_conv_id = row[:5]
    control_id, binding_generation = row[5:7]
    if (
        not all(
            isinstance(value, str)
            for value in (account_id, thread_type, thread_key, old_conv_id, control_id)
        )
        or not isinstance(user_id, int)
        or not isinstance(binding_generation, int)
    ):
        raise StateError("Pending Messaging reset identity is invalid.")
    cancellation_input_id = _cancel_safe_reset_inputs(
        conn,
        conv_id=old_conv_id,
        user_id=user_id,
    )
    if cancellation_input_id is not None:
        return {
            "status": "reset_waiting",
            "conv_id": old_conv_id,
            "user_id": user_id,
            "cancellation_input_id": cancellation_input_id,
        }
    account = conn.execute(
        """
        SELECT label, platform, model_settings_json, locale, lifecycle_generation,
               lifecycle_state
        FROM messaging_accounts WHERE account_id = ? AND user_id = ?
        """,
        (account_id, user_id),
    ).fetchone()
    if account is None or account[5] not in ("enabled", "degraded", "disabled"):
        return {"status": "reset_abandoned", "conv_id": old_conv_id, "user_id": user_id}
    if not isinstance(account[0], str) or not isinstance(account[1], str):
        raise StateError("Pending Messaging reset account is invalid.")
    if not isinstance(account[3], str) or not isinstance(account[4], int):
        raise StateError("Pending Messaging reset account state is invalid.")
    model_settings = parse_json_dict(account[2], field="Messaging account model settings")
    old_conversation = conn.execute(
        "SELECT title FROM webui_conversations WHERE id = ? AND user_id = ?",
        (old_conv_id, user_id),
    ).fetchone()
    if old_conversation is None or not isinstance(old_conversation[0], str):
        raise StateError("Pending Messaging reset conversation is unavailable.")
    new_conv_id = _replacement_conversation_id(control_id)
    exchange = sync_append_conversation_control_exchange(
        conn,
        conv_id=old_conv_id,
        user_id=user_id,
        command_text="/new",
        response_text=resolve_messaging_response_text(account[3], "new_completed"),
        completed_at_ms=completed_at_ms,
    )
    conn.execute(
        """
        UPDATE webui_conversations
        SET model_settings = ?, messaging_account_label = ?,
            input_generation = input_generation + 1
        WHERE id = ? AND user_id = ? AND is_messaging = 1
        """,
        (account[2], account[0], old_conv_id, user_id),
    )
    _ = sync_create_conversation(
        conn,
        user_id,
        old_conversation[0],
        model_settings,
        False,
        new_conv_id,
        messaging_platform=account[1],
        messaging_account_label=account[0],
        messaging_account_snapshot_id=account_id,
    )
    binding_updated = conn.execute(
        """
        UPDATE messaging_thread_bindings
        SET conv_id = ?, pending_reset_control_id = NULL, pending_reset_state = NULL,
            updated_at_ms = ?
        WHERE account_id = ? AND user_id = ? AND remote_thread_type = ?
          AND remote_thread_key = ? AND conv_id = ?
          AND pending_reset_control_id = ? AND pending_reset_state = 'accepted'
          AND binding_generation = ?
        """,
        (
            new_conv_id,
            completed_at_ms,
            account_id,
            user_id,
            thread_type,
            thread_key,
            old_conv_id,
            control_id,
            binding_generation,
        ),
    ).rowcount
    if binding_updated != 1:
        raise ConflictError("Messaging reset completion fence changed.")
    conn.execute(
        """
        UPDATE messaging_ingress_events
        SET result_conv_id = ?, account_generation = ?, binding_generation = ?,
            diagnostic_code = NULL, processed_at_ms = ?
        WHERE ingress_id = ? AND old_conv_id = ? AND result_conv_id IS NULL
        """,
        (
            new_conv_id,
            account[4],
            binding_generation,
            completed_at_ms,
            control_id,
            old_conv_id,
        ),
    )
    source_message_id = exchange["source_message_id"]
    if not isinstance(source_message_id, int):
        raise StateError("Messaging reset control response identity is invalid.")
    sync_ensure_conversation_control_completed_event(
        conn,
        control_id=control_id,
        user_id=user_id,
        conv_id=old_conv_id,
        target_conv_id=new_conv_id,
        source_message_id=source_message_id,
        created_at_ms=completed_at_ms,
    )
    return {
        "status": "reset_completed",
        "ingress_id": control_id,
        "control_id": control_id,
        "conv_id": new_conv_id,
        "old_conv_id": old_conv_id,
        "user_id": user_id,
        "conversation_created": True,
        "old_last_modified_at_ms": exchange["last_modified_at_ms"],
    }


def sync_complete_pending_messaging_resets(
    conn: sqlite3.Connection,
) -> list[JSONDict]:
    rows = conn.execute(
        """
        SELECT account_id, user_id, remote_thread_type, remote_thread_key, conv_id,
               pending_reset_control_id, binding_generation
        FROM messaging_thread_bindings
        WHERE pending_reset_state = 'accepted' AND pending_reset_control_id IS NOT NULL
        ORDER BY updated_at_ms ASC, account_id ASC, remote_thread_key ASC
        LIMIT 100
        """,
    ).fetchall()
    completed_at_ms = epoch_ms()
    return [_complete_reset_row(conn, row, completed_at_ms) for row in rows]

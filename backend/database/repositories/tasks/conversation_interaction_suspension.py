"""SoAI - Atomic task-owned conversation interaction suspension [backend/database/repositories/tasks/conversation_interaction_suspension.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import sqlite3

from core.database.task_requests import ConversationInteractionCheckpointRequest
from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict
from database.repositories.tasks.conversation_interaction_events import (
    sync_ensure_conversation_interaction_required_event,
)

__all__ = ("sync_suspend_conversation_input_for_interaction",)

_INTERACTION_TYPES = frozenset(("tool_approval", "ask_user", "vault_secret_request"))
_SUSPENSION_PHASES = frozenset(
    ("before_approved_tool", "awaiting_ask_user_result", "awaiting_vault_secret")
)


def _require_checkpoint(checkpoint: ConversationInteractionCheckpointRequest) -> None:
    text_values = (
        checkpoint.input_id,
        checkpoint.conv_id,
        checkpoint.claim_owner,
        checkpoint.server_boot_id,
        checkpoint.turn_id,
        checkpoint.tool_call_id,
        checkpoint.reply_token,
        checkpoint.focus_nonce,
    )
    if any(not value.strip() for value in text_values):
        raise StateError("Conversation interaction checkpoint identity is invalid.")
    if checkpoint.user_id <= 0 or checkpoint.claim_generation <= 0:
        raise StateError("Conversation interaction checkpoint claim is invalid.")
    if checkpoint.iteration_index < 0 or checkpoint.expires_at_ms <= 0:
        raise StateError("Conversation interaction checkpoint chronology is invalid.")
    if checkpoint.interaction_type not in _INTERACTION_TYPES:
        raise StateError("Conversation interaction type is invalid.")
    if checkpoint.suspension_phase not in _SUSPENSION_PHASES:
        raise StateError("Conversation interaction suspension phase is invalid.")
    if checkpoint.argument_hash is not None and len(checkpoint.argument_hash) != 64:
        raise StateError("Conversation interaction argument hash is invalid.")


def _read_input_row(
    conn: sqlite3.Connection,
    checkpoint: ConversationInteractionCheckpointRequest,
) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT input.transport_origin, input.source_metadata_json,
               ingress.account_id, ingress.platform, ingress.remote_thread_type,
               ingress.remote_thread_key, ingress.sender_id,
               account.lifecycle_state, account.lifecycle_generation,
               binding.binding_generation,
               CASE WHEN sender.sender_id IS NULL THEN 0 ELSE 1 END
        FROM webui_conversation_inputs AS input
        LEFT JOIN messaging_ingress_events AS ingress
          ON ingress.ingress_id = input.messaging_ingress_id
        LEFT JOIN messaging_accounts AS account
          ON account.account_id = ingress.account_id AND account.user_id = ingress.user_id
        LEFT JOIN messaging_thread_bindings AS binding
          ON binding.account_id = ingress.account_id AND binding.user_id = ingress.user_id
         AND binding.remote_thread_type = ingress.remote_thread_type
         AND binding.remote_thread_key = ingress.remote_thread_key
         AND binding.conv_id = input.conv_id
        LEFT JOIN messaging_authorized_senders AS sender
          ON sender.account_id = ingress.account_id AND sender.user_id = ingress.user_id
         AND sender.sender_id = ingress.sender_id
        WHERE input.input_id = ? AND input.conv_id = ? AND input.user_id = ?
          AND input.state = 'running' AND input.claim_generation = ?
          AND input.claim_owner = ? AND input.claim_server_boot_id = ?
        LIMIT 1
        """,
        (
            checkpoint.input_id,
            checkpoint.conv_id,
            checkpoint.user_id,
            checkpoint.claim_generation,
            checkpoint.claim_owner,
            checkpoint.server_boot_id,
        ),
    ).fetchone()
    if not isinstance(row, sqlite3.Row):
        raise StateError("Conversation interaction input claim is no longer active.")
    return row


def _require_persisted_turn_checkpoint(
    conn: sqlite3.Connection,
    checkpoint: ConversationInteractionCheckpointRequest,
) -> None:
    row = conn.execute(
        """
        SELECT tool_calls_json FROM webui_agent_turns
        WHERE conv_id = ? AND user_id = ? AND turn_id = ? AND status = 'running'
          AND iteration_index = ?
        LIMIT 1
        """,
        (
            checkpoint.conv_id,
            checkpoint.user_id,
            checkpoint.turn_id,
            checkpoint.iteration_index,
        ),
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        raise StateError("Conversation interaction agent checkpoint is unavailable.")
    tool_calls = parse_json_dict(f'{{"calls":{row[0]}}}', field="Agent checkpoint").get("calls")
    if not isinstance(tool_calls, list) or not any(
        isinstance(call, dict) and call.get("id") == checkpoint.tool_call_id for call in tool_calls
    ):
        raise StateError("Conversation interaction tool checkpoint is unavailable.")


def sync_suspend_conversation_input_for_interaction(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    checkpoint: ConversationInteractionCheckpointRequest,
    created_at_ms: int,
) -> None:
    _require_checkpoint(checkpoint)
    row = _read_input_row(conn, checkpoint)
    if row[0] == "chat":
        return
    if row[0] != "messaging":
        raise StateError("Conversation interaction transport origin is invalid.")
    _require_persisted_turn_checkpoint(conn, checkpoint)
    source_metadata = parse_json_dict(row[1], field="Conversation input source metadata")
    if not all(isinstance(row[index], str) and row[index] for index in (2, 3, 4, 5, 6)):
        raise StateError("Conversation interaction Messaging route is invalid.")
    if row[7] not in {"enabled", "degraded"} or row[10] != 1:
        raise StateError("Conversation interaction Messaging account is unavailable.")
    if not isinstance(row[8], int) or not isinstance(row[9], int):
        raise StateError("Conversation interaction Messaging generation is invalid.")
    if source_metadata.get("account_generation") != row[8]:
        raise StateError("Conversation interaction account generation is stale.")
    if source_metadata.get("binding_generation") != row[9]:
        raise StateError("Conversation interaction binding generation is stale.")
    generation_row = conn.execute(
        "SELECT COALESCE(suspension_generation, 0) + 1 FROM webui_conversation_inputs WHERE input_id = ?",
        (checkpoint.input_id,),
    ).fetchone()
    checkpoint_generation = generation_row[0] if generation_row is not None else None
    if not isinstance(checkpoint_generation, int) or checkpoint_generation <= 0:
        raise StateError("Conversation interaction checkpoint generation is invalid.")
    updated = conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = 'input_required', agent_turn_id = ?, task_id = ?,
            suspension_phase = ?, suspension_iteration = ?,
            suspension_tool_call_id = ?, suspension_generation = ?,
            input_required_at_ms = ?, updated_at_ms = ?
        WHERE input_id = ? AND state = 'running' AND claim_generation = ?
          AND claim_owner = ? AND claim_server_boot_id = ?
        """,
        (
            checkpoint.turn_id,
            task_id,
            checkpoint.suspension_phase,
            checkpoint.iteration_index,
            checkpoint.tool_call_id,
            checkpoint_generation,
            created_at_ms,
            created_at_ms,
            checkpoint.input_id,
            checkpoint.claim_generation,
            checkpoint.claim_owner,
            checkpoint.server_boot_id,
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Conversation interaction input suspension lost its claim.")
    route_id = f"interaction_{hashlib.sha256(task_id.encode()).hexdigest()[:24]}"
    conn.execute(
        """
        INSERT INTO messaging_interaction_routes (
            route_id, account_id, user_id, account_generation, binding_generation,
            remote_thread_type, remote_thread_key, conv_id, input_id, task_id,
            interaction_type, originating_sender_id, tool_call_id, argument_hash,
            reply_token_hash, focus_nonce_hash, checkpoint_generation, state,
            expires_at_ms, created_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """,
        (
            route_id,
            row[2],
            checkpoint.user_id,
            row[8],
            row[9],
            row[4],
            row[5],
            checkpoint.conv_id,
            checkpoint.input_id,
            task_id,
            checkpoint.interaction_type,
            row[6],
            checkpoint.tool_call_id,
            checkpoint.argument_hash,
            hashlib.sha256(checkpoint.reply_token.casefold().encode()).hexdigest(),
            hashlib.sha256(checkpoint.focus_nonce.encode()).hexdigest(),
            checkpoint_generation,
            checkpoint.expires_at_ms,
            created_at_ms,
        ),
    )
    sync_ensure_conversation_interaction_required_event(
        conn,
        route_id=route_id,
        task_id=task_id,
        input_id=checkpoint.input_id,
        user_id=checkpoint.user_id,
        conv_id=checkpoint.conv_id,
        interaction_type=checkpoint.interaction_type,
        reply_token=checkpoint.reply_token,
        focus_nonce=checkpoint.focus_nonce,
        created_at_ms=created_at_ms,
    )

"""SoAI - Task interaction secret claim and consumption persistence [backend/database/repositories/tasks/conversation_interaction_secrets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError
from core.security.secret_crypto import encrypt_required_secret
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, is_json_list

__all__ = (
    "InteractionSecretCiphertextClaim",
    "InteractionSecretEffectUnknownClaim",
    "sync_claim_interaction_secret",
    "sync_consume_interaction_secret_after_tool_checkpoint",
    "sync_consume_interaction_secrets_after_turn_checkpoint",
    "sync_mark_interaction_secret_downstream_started",
    "sync_stage_interaction_secret_resolution",
)


@dataclass(frozen=True, slots=True)
class InteractionSecretCiphertextClaim:
    task_id: str
    user_id: int
    conv_id: str
    claim_generation: int
    claim_owner: str
    ciphertext: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class InteractionSecretEffectUnknownClaim:
    task_id: str


def sync_stage_interaction_secret_resolution(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    *,
    task_id: str,
    user_id: int,
    conv_id: str,
    checkpoint_generation: int,
    resolution_payload: JSONDict,
    expires_at_ms: int,
    staged_at_ms: int,
) -> None:
    checkpoint = conn.execute(
        """
        SELECT 1
        FROM webui_conversation_inputs AS input
        JOIN unified_tasks AS task ON task.task_id = input.task_id
        WHERE input.task_id = ? AND input.user_id = ? AND input.conv_id = ?
          AND input.state = 'input_required' AND input.suspension_generation = ?
          AND task.status = 'input_required'
        """,
        (task_id, user_id, conv_id, checkpoint_generation),
    ).fetchone()
    if checkpoint is None or expires_at_ms <= staged_at_ms:
        raise StateError("Interaction secret resolution checkpoint is invalid.")
    ciphertext = encrypt_required_secret(
        fernets,
        serialize_json_compact_stable(resolution_payload),
        label="staged interaction secret resolution",
    )
    conn.execute(
        """
        INSERT INTO task_interaction_secret_handoffs (
            task_id, user_id, conv_id, checkpoint_generation,
            secret_ciphertext, state, claim_generation, expires_at_ms,
            created_at_ms, updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, 'resolution_staged', 0, ?, ?, ?)
        """,
        (
            task_id,
            user_id,
            conv_id,
            checkpoint_generation,
            ciphertext,
            expires_at_ms,
            staged_at_ms,
            staged_at_ms,
        ),
    )


def sync_claim_interaction_secret(
    conn: sqlite3.Connection,
    task_id: str,
    user_id: int,
    conv_id: str,
    claim_owner: str,
    claimed_at_ms: int,
) -> InteractionSecretCiphertextClaim | InteractionSecretEffectUnknownClaim | None:
    row = conn.execute(
        """
        SELECT user_id, conv_id, secret_ciphertext, state, claim_generation,
               expires_at_ms, downstream_tool_call_id
        FROM task_interaction_secret_handoffs
        WHERE task_id = ?
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    if row[0] != user_id or row[1] != conv_id:
        raise StateError("Task interaction secret ownership is invalid.")
    if not isinstance(row[3], str):
        raise StateError("Task interaction secret row is invalid.")
    if not isinstance(row[4], int) or not isinstance(row[5], int):
        raise StateError("Task interaction secret claim state is invalid.")
    if row[5] <= claimed_at_ms:
        conn.execute(
            """
            UPDATE task_interaction_secret_handoffs
            SET state = 'expired', secret_ciphertext = NULL, updated_at_ms = ?
            WHERE task_id = ?
            """,
            (claimed_at_ms, task_id),
        )
        return None
    if row[3] == "downstream_started" or row[6] is not None:
        if sync_consume_interaction_secret_after_tool_checkpoint(
            conn,
            task_id=task_id,
            consumed_at_ms=claimed_at_ms,
        ):
            return None
        conn.execute(
            """
            UPDATE task_interaction_secret_handoffs
            SET state = 'effect_unknown', secret_ciphertext = NULL, updated_at_ms = ?
            WHERE task_id = ? AND state = 'downstream_started'
            """,
            (claimed_at_ms, task_id),
        )
        return InteractionSecretEffectUnknownClaim(task_id=task_id)
    if row[3] == "effect_unknown":
        return InteractionSecretEffectUnknownClaim(task_id=task_id)
    if row[3] not in {"pending", "claimed"}:
        return None
    if not isinstance(row[2], str):
        raise StateError("Task interaction secret ciphertext is unavailable.")
    normalized_claim_owner = claim_owner.strip()
    if not normalized_claim_owner:
        raise StateError("Task interaction secret claim owner is invalid.")
    claim_generation = row[4] + 1
    updated = conn.execute(
        """
        UPDATE task_interaction_secret_handoffs
        SET state = 'claimed', claim_generation = ?, claimed_by = ?,
            updated_at_ms = ?
        WHERE task_id = ? AND state IN ('pending', 'claimed')
          AND claim_generation = ? AND downstream_tool_call_id IS NULL
        """,
        (claim_generation, normalized_claim_owner, claimed_at_ms, task_id, row[4]),
    ).rowcount
    if updated != 1:
        raise StateError("Task interaction secret claim lost its generation fence.")
    return InteractionSecretCiphertextClaim(
        task_id=task_id,
        user_id=user_id,
        conv_id=conv_id,
        claim_generation=claim_generation,
        claim_owner=normalized_claim_owner,
        ciphertext=row[2],
    )


def sync_mark_interaction_secret_downstream_started(
    conn: sqlite3.Connection,
    task_id: str,
    claim_generation: int,
    claim_owner: str,
    tool_call_id: str,
    started_at_ms: int,
) -> bool:
    normalized_tool_call_id = tool_call_id.strip()
    if not normalized_tool_call_id:
        raise StateError("Secret-consuming tool call identity is invalid.")
    updated = conn.execute(
        """
        UPDATE task_interaction_secret_handoffs
        SET state = 'downstream_started', downstream_tool_call_id = ?,
            downstream_started_at_ms = ?, updated_at_ms = ?
        WHERE task_id = ? AND state = 'claimed' AND claim_generation = ?
          AND claimed_by = ? AND downstream_tool_call_id IS NULL
        """,
        (
            normalized_tool_call_id,
            started_at_ms,
            started_at_ms,
            task_id,
            claim_generation,
            claim_owner,
        ),
    ).rowcount
    return updated == 1


def sync_consume_interaction_secret_after_tool_checkpoint(
    conn: sqlite3.Connection,
    task_id: str,
    consumed_at_ms: int,
) -> bool:
    row = conn.execute(
        """
        SELECT handoff.downstream_tool_call_id, turn.tool_calls_json,
               turn.tool_results_json
        FROM task_interaction_secret_handoffs AS handoff
        JOIN webui_conversation_inputs AS input ON input.task_id = handoff.task_id
        JOIN webui_agent_turns AS turn
          ON turn.turn_id = input.agent_turn_id
         AND turn.iteration_index = input.suspension_iteration
        WHERE handoff.task_id = ? AND handoff.state = 'downstream_started'
        """,
        (task_id,),
    ).fetchone()
    if row is None:
        return False
    if not all(isinstance(row[index], str) for index in (0, 1, 2)):
        raise StateError("Task interaction secret tool checkpoint is invalid.")
    tool_calls = parse_json_value(row[1], field="Agent tool calls")
    tool_results = parse_json_value(row[2], field="Agent tool results")
    if not is_json_list(tool_calls) or not is_json_list(tool_results):
        raise StateError("Task interaction secret tool checkpoint is invalid.")
    tool_index: int | None = None
    for index, tool_call in enumerate(tool_calls):
        if isinstance(tool_call, dict) and tool_call.get("id") == row[0]:
            tool_index = index
            break
    if tool_index is None or tool_index >= len(tool_results):
        return False
    deleted = conn.execute(
        """
        DELETE FROM task_interaction_secret_handoffs
        WHERE task_id = ? AND state = 'downstream_started'
          AND downstream_tool_call_id = ? AND updated_at_ms <= ?
        """,
        (task_id, row[0], consumed_at_ms),
    ).rowcount
    return deleted == 1


def sync_consume_interaction_secrets_after_turn_checkpoint(
    conn: sqlite3.Connection,
    turn_id: str,
    iteration_index: int,
    consumed_at_ms: int,
) -> int:
    rows = conn.execute(
        """
        SELECT handoff.task_id
        FROM task_interaction_secret_handoffs AS handoff
        JOIN webui_conversation_inputs AS input ON input.task_id = handoff.task_id
        WHERE handoff.state = 'downstream_started'
          AND input.agent_turn_id = ? AND input.suspension_iteration = ?
        ORDER BY handoff.created_at_ms ASC, handoff.task_id ASC
        """,
        (turn_id, iteration_index),
    ).fetchall()
    consumed = 0
    for row in rows:
        task_id = row[0] if row else None
        if not isinstance(task_id, str):
            raise StateError("Task interaction secret checkpoint identity is invalid.")
        if sync_consume_interaction_secret_after_tool_checkpoint(
            conn,
            task_id=task_id,
            consumed_at_ms=consumed_at_ms,
        ):
            consumed += 1
    return consumed

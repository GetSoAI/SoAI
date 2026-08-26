"""SoAI - Atomic conversation interaction finalization mutations [backend/database/repositories/tasks/conversation_interaction_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError
from core.security.secret_crypto import encrypt_required_secret
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict
from core.tasks.interaction_mutations import ConversationInteractionMutation
from core.web.site_scope_codec import coerce_site_scope_json_dict
from database.repositories.users.password_vault_writes import (
    sync_create_password_vault_credential,
)
from database.repositories.users.user_preference_mutations import (
    sync_write_tool_approval_permission,
)

__all__ = ("sync_apply_conversation_interaction_mutation",)


def _read_task_identity(
    conn: sqlite3.Connection,
    task_id: str,
) -> tuple[int, str, str]:
    row = conn.execute(
        "SELECT user_id, owner_id, metadata FROM unified_tasks WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    if (
        row is None
        or not isinstance(row[0], int)
        or not isinstance(row[1], str)
        or not isinstance(row[2], str)
    ):
        raise StateError("Conversation interaction task identity is invalid.")
    return row[0], row[1], row[2]


def _require_checkpoint_generation(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    expected_generation: int | None,
) -> int:
    row = conn.execute(
        "SELECT suspension_generation FROM webui_conversation_inputs WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    if row is None:
        if expected_generation is not None:
            raise StateError("Conversation interaction checkpoint is unavailable.")
        return 0
    generation = row[0]
    if not isinstance(generation, int) or generation <= 0:
        raise StateError("Conversation interaction checkpoint generation is invalid.")
    if expected_generation is not None and generation != expected_generation:
        raise StateError("Conversation interaction checkpoint generation is stale.")
    return generation


def _write_remembered_tool_permission(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    tool_permission: str,
) -> None:
    sync_write_tool_approval_permission(conn, user_id, tool_permission)


def _write_vault_secret_handoff(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    *,
    task_id: str,
    task_user_id: int,
    task_conv_id: str,
    checkpoint_generation: int,
    mutation: ConversationInteractionMutation,
    created_at_ms: int,
) -> None:
    handoff = mutation.vault_secret_handoff
    if handoff is None:
        return
    if handoff.user_id != task_user_id or handoff.conv_id != task_conv_id:
        raise StateError("Vault secret handoff task ownership is invalid.")
    if (
        handoff.checkpoint_generation is not None
        and handoff.checkpoint_generation != checkpoint_generation
    ):
        raise StateError("Vault secret handoff checkpoint generation is stale.")
    if handoff.expires_at_ms <= created_at_ms:
        raise StateError("Vault secret handoff expiry is invalid.")
    if handoff.saved_credential_id is not None:
        if handoff.saved_credential_label is None:
            raise StateError("Vault secret credential label is unavailable.")
        sync_create_password_vault_credential(
            conn,
            fernets,
            handoff.saved_credential_id,
            handoff.user_id,
            handoff.saved_credential_label,
            handoff.scope,
            handoff.username,
            handoff.password,
        )
    secret_payload = serialize_json_compact_stable(
        {
            "scope": coerce_site_scope_json_dict(handoff.scope),
            "username": handoff.username,
            "password": handoff.password,
        },
    )
    ciphertext = encrypt_required_secret(
        fernets,
        secret_payload,
        label="task interaction secret handoff",
    )
    existing = conn.execute(
        "SELECT state FROM task_interaction_secret_handoffs WHERE task_id = ?",
        (task_id,),
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO task_interaction_secret_handoffs (
                task_id, user_id, conv_id, checkpoint_generation,
                secret_ciphertext, state, claim_generation, expires_at_ms,
                created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)
            """,
            (
                task_id,
                handoff.user_id,
                handoff.conv_id,
                checkpoint_generation,
                ciphertext,
                handoff.expires_at_ms,
                created_at_ms,
                created_at_ms,
            ),
        )
        return
    updated = conn.execute(
        """
        UPDATE task_interaction_secret_handoffs
        SET secret_ciphertext = ?, state = 'pending', expires_at_ms = ?,
            updated_at_ms = ?
        WHERE task_id = ? AND user_id = ? AND conv_id = ?
          AND checkpoint_generation = ? AND state = 'resolution_staged'
        """,
        (
            ciphertext,
            handoff.expires_at_ms,
            created_at_ms,
            task_id,
            handoff.user_id,
            handoff.conv_id,
            checkpoint_generation,
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Staged vault secret resolution is no longer valid.")


def sync_apply_conversation_interaction_mutation(
    conn: sqlite3.Connection,
    fernets: tuple[Fernet, ...],
    *,
    task_id: str,
    mutation: ConversationInteractionMutation,
    created_at_ms: int,
) -> None:
    task_user_id, task_conv_id, metadata_json = _read_task_identity(conn, task_id)
    metadata = parse_json_dict(metadata_json, field="Conversation interaction task metadata")
    interaction_type = metadata.get("interaction_type")
    checkpoint_generation = _require_checkpoint_generation(
        conn,
        task_id=task_id,
        expected_generation=mutation.checkpoint_generation,
    )
    tool_permission = mutation.remembered_tool_permission
    if tool_permission is not None:
        if interaction_type != "tool_approval" or not tool_permission.strip():
            raise StateError("Remembered tool approval mutation is invalid.")
        _write_remembered_tool_permission(
            conn,
            user_id=task_user_id,
            tool_permission=tool_permission,
        )
    if mutation.vault_secret_handoff is not None:
        if interaction_type != "vault_secret_request":
            raise StateError("Vault secret handoff task type is invalid.")
        _write_vault_secret_handoff(
            conn,
            fernets,
            task_id=task_id,
            task_user_id=task_user_id,
            task_conv_id=task_conv_id,
            checkpoint_generation=checkpoint_generation,
            mutation=mutation,
            created_at_ms=created_at_ms,
        )

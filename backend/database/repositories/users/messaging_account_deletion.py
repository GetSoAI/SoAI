"""SoAI - Durable Messaging account deletion lifecycle [backend/database/repositories/users/messaging_account_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError
from core.messaging.account_models import (
    MessagingAccountDeleteFence,
    MessagingActiveInputIdentity,
    MessagingConversationVersion,
)
from core.tasks.status_policy import ACTIVE_TASK_STATUS_VALUES, active_task_status_placeholders
from core.timing.epoch import epoch_ms
from database.repositories.users.conversation_input_terminal_events import (
    sync_ensure_conversation_input_terminal_event,
)
from database.repositories.users.messaging_account_reads import sync_read_messaging_account
from database.repositories.users.messaging_delivery_fencing import (
    sync_fence_messaging_deliveries,
)
from database.repositories.users.messaging_interaction_fencing import (
    sync_fence_messaging_interactions,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_begin_messaging_account_delete",
    "sync_finalize_messaging_account_delete",
)


def sync_begin_messaging_account_delete(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
    expected_revision: int,
) -> MessagingAccountDeleteFence | None:
    now_ms = epoch_ms()
    updated = conn.execute(
        """
        UPDATE messaging_accounts
        SET lifecycle_state = 'deleting', lifecycle_generation = lifecycle_generation + 1,
            revision = revision + 1, updated_at_ms = ?
        WHERE user_id = ? AND account_id = ? AND revision = ?
          AND lifecycle_state != 'deleting'
        """,
        (now_ms, user_id, account_id, expected_revision),
    ).rowcount
    if updated != 1:
        existing = sync_read_messaging_account(conn, user_id, account_id)
        if existing is None:
            return None
        if existing.get("lifecycle_state") == "deleting":
            return _read_delete_fence(conn, existing, user_id, account_id)
        raise ConflictError("Messaging account changed before deletion was fenced.")
    active_inputs = _read_delete_active_inputs(conn, user_id, account_id)
    cancelled_rows = conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = 'cancelled', terminal_code = 'messaging_account_deleted',
            terminal_args_json = '{}', terminal_at_ms = ?, updated_at_ms = ?
        WHERE transport_origin = 'messaging'
          AND state IN ('pending', 'materializing', 'input_required')
          AND conv_id IN (
              SELECT conv_id FROM messaging_thread_bindings
              WHERE account_id = ? AND user_id = ?
          )
        RETURNING input_id, conv_id, user_id
        """,
        (now_ms, now_ms, account_id, user_id),
    ).fetchall()
    for row in cancelled_rows:
        sync_ensure_conversation_input_terminal_event(
            conn,
            input_id=str(row[0]),
            user_id=int(row[2]),
            conv_id=str(row[1]),
            source_message_id=None,
            terminal_state="cancelled",
            terminal_code="messaging_account_deleted",
            created_at_ms=now_ms,
        )
    unknown_rows = conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = 'effect_unknown', terminal_code = 'messaging_account_deleted_effect_unknown',
            terminal_args_json = '{}', terminal_at_ms = ?, updated_at_ms = ?
        WHERE transport_origin = 'messaging' AND state = 'running'
          AND conv_id IN (
              SELECT conv_id FROM messaging_thread_bindings
              WHERE account_id = ? AND user_id = ?
          )
        RETURNING input_id, conv_id, user_id
        """,
        (now_ms, now_ms, account_id, user_id),
    ).fetchall()
    for row in unknown_rows:
        sync_ensure_conversation_input_terminal_event(
            conn,
            input_id=str(row[0]),
            user_id=int(row[2]),
            conv_id=str(row[1]),
            source_message_id=None,
            terminal_state="effect_unknown",
            terminal_code="messaging_account_deleted_effect_unknown",
            created_at_ms=now_ms,
        )
    interaction_task_ids = sync_fence_messaging_interactions(
        conn,
        account_id=account_id,
        user_id=user_id,
        resolved_at_ms=now_ms,
    )
    sync_fence_messaging_deliveries(
        conn,
        account_id=account_id,
        user_id=user_id,
        failure_code="messaging_account_deleted",
        now_ms=now_ms,
    )
    fenced = sync_read_messaging_account(conn, user_id, account_id)
    if fenced is None:
        return None
    return MessagingAccountDeleteFence(
        account=fenced,
        task_ids=_delete_task_ids(active_inputs, interaction_task_ids),
        active_inputs=active_inputs,
    )


def _read_delete_active_inputs(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
) -> tuple[MessagingActiveInputIdentity, ...]:
    rows = conn.execute(
        """
        SELECT input.input_id, input.conv_id, input.user_id, input.task_id
        FROM webui_conversation_inputs AS input
        JOIN messaging_thread_bindings AS binding ON binding.conv_id = input.conv_id
        WHERE binding.account_id = ? AND binding.user_id = ?
          AND input.transport_origin = 'messaging'
          AND input.state IN ('materializing', 'running', 'input_required')
        ORDER BY input.accepted_at_ms ASC, input.id ASC
        """,
        (account_id, user_id),
    ).fetchall()
    return tuple(
        MessagingActiveInputIdentity(
            input_id=str(row[0]),
            conv_id=str(row[1]),
            user_id=int(row[2]),
            task_id=str(row[3]) if isinstance(row[3], str) else None,
        )
        for row in rows
    )


def _delete_task_ids(
    active_inputs: tuple[MessagingActiveInputIdentity, ...],
    interaction_task_ids: tuple[str, ...],
) -> tuple[str, ...]:
    active_task_ids = {active.task_id for active in active_inputs if active.task_id is not None}
    return tuple(sorted(active_task_ids | set(interaction_task_ids)))


def _read_delete_fence(
    conn: sqlite3.Connection,
    account: JSONDict,
    user_id: int,
    account_id: str,
) -> MessagingAccountDeleteFence:
    task_rows = conn.execute(
        f"""
        SELECT DISTINCT route.task_id
        FROM messaging_interaction_routes AS route
        JOIN unified_tasks AS task ON task.task_id = route.task_id
        WHERE route.account_id = ? AND route.user_id = ?
          AND task.status IN ({active_task_status_placeholders()})
        ORDER BY route.task_id
        """,
        (account_id, user_id, *ACTIVE_TASK_STATUS_VALUES),
    ).fetchall()
    return MessagingAccountDeleteFence(
        account=account,
        task_ids=tuple(str(row[0]) for row in task_rows),
        active_inputs=(),
    )


def sync_finalize_messaging_account_delete(
    conn: sqlite3.Connection,
    user_id: int,
    account_id: str,
    lifecycle_generation: int,
) -> tuple[MessagingConversationVersion, ...] | None:
    account = sync_read_messaging_account(conn, user_id, account_id)
    if account is None:
        return None
    if account.get("lifecycle_state") != "deleting":
        raise ConflictError("Messaging account deletion has not been fenced.")
    if account.get("lifecycle_generation") != lifecycle_generation:
        raise ConflictError("Messaging account deletion generation changed.")
    active_input = conn.execute(
        """
        SELECT 1
        FROM webui_conversation_inputs AS input
        JOIN messaging_thread_bindings AS binding ON binding.conv_id = input.conv_id
        WHERE binding.account_id = ? AND binding.user_id = ?
          AND input.transport_origin = 'messaging'
          AND input.state IN ('materializing', 'running', 'input_required')
        LIMIT 1
        """,
        (account_id, user_id),
    ).fetchone()
    if active_input is not None:
        raise ConflictError("Messaging account deletion is waiting for accepted work to settle.")
    now_ms = epoch_ms()
    conn.execute(
        """
        UPDATE webui_conversations
        SET model_settings = (
                SELECT model_settings_json FROM messaging_accounts WHERE account_id = ?
            ),
            messaging_account_label = (
                SELECT label FROM messaging_accounts WHERE account_id = ?
            ),
            last_modified_at_ms = MAX(last_modified_at_ms + 1, ?)
        WHERE user_id = ? AND id IN (
            SELECT conv_id FROM messaging_thread_bindings WHERE account_id = ? AND user_id = ?
        )
        """,
        (account_id, account_id, now_ms, user_id, account_id, user_id),
    )
    conversation_rows = conn.execute(
        """
        SELECT conversation.id, conversation.last_modified_at_ms
        FROM messaging_thread_bindings AS binding
        JOIN webui_conversations AS conversation
          ON conversation.id = binding.conv_id AND conversation.user_id = binding.user_id
        WHERE binding.account_id = ? AND binding.user_id = ?
        ORDER BY conversation.id
        """,
        (account_id, user_id),
    ).fetchall()
    deleted = conn.execute(
        """
        DELETE FROM messaging_accounts
        WHERE account_id = ? AND user_id = ? AND lifecycle_state = 'deleting'
          AND lifecycle_generation = ?
        """,
        (account_id, user_id, lifecycle_generation),
    ).rowcount
    if deleted != 1:
        raise ConflictError("Messaging account deletion fence changed.")
    return tuple(
        MessagingConversationVersion(
            conv_id=str(row[0]),
            last_modified_at_ms=int(row[1]),
        )
        for row in conversation_rows
    )

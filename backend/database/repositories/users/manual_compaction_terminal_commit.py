"""SoAI - Manual compaction terminal commit transaction [backend/database/repositories/users/manual_compaction_terminal_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.database.requests import (
    ManualCompactionTerminalCommitRequest,
    ManualCompactionTerminalCommitResult,
)
from database.repositories.users.agent_event_sequence_transactions import (
    sync_reserve_agent_event_sequence_range,
)
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
)
from database.repositories.users.manual_compaction_terminal_messages import (
    sync_commit_manual_compaction_message_rows,
)
from database.repositories.users.manual_compaction_terminal_turns import (
    sync_commit_manual_compaction_turn_state,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages

__all__ = ("sync_commit_manual_compaction_terminal",)


def sync_commit_manual_compaction_terminal(
    conn: sqlite3.Connection,
    request: ManualCompactionTerminalCommitRequest,
) -> ManualCompactionTerminalCommitResult:
    ensure_conversation_owned(conn, request.conv_id, int(request.user_id))
    assistant_at_ms, message_index = sync_commit_manual_compaction_message_rows(conn, request)
    tool_completion_sequence, turn_terminal_sequence = sync_reserve_agent_event_sequence_range(
        conn,
        conv_id=request.conv_id,
        user_id=int(request.user_id),
        count=2,
        updated_at_ms=int(request.completed_at_ms),
    )
    sync_commit_manual_compaction_turn_state(
        conn,
        request,
        message_index=message_index,
        tool_completion_sequence=tool_completion_sequence,
        turn_terminal_sequence=turn_terminal_sequence,
    )
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, request.conv_id)
    return ManualCompactionTerminalCommitResult(
        assistant_at_ms=int(assistant_at_ms),
        message_index=int(message_index),
        message_count=sync_count_stored_messages(conn, request.conv_id),
        last_modified_at_ms=int(last_modified_at_ms),
        tool_completion_sequence=int(tool_completion_sequence),
        turn_terminal_sequence=int(turn_terminal_sequence),
    )

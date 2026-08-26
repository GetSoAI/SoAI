"""SoAI - Conversation start snapshot reads [backend/database/repositories/users/messages_start_snapshot_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from core.conversations.conversation_start_snapshot import ConversationStartSnapshot
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.canonical_agent_history_reads import (
    query_canonical_agent_history,
)
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.message_counting_queries import (
    load_conversation_message_count,
)
from database.repositories.users.message_row_mapping import (
    attach_assistant_event_timeline,
    build_message_payload_from_row,
)
from database.repositories.users.message_tool_projection_attachment import (
    attach_tool_call_projections,
)
from database.repositories.users.read_transactions import run_user_read_transaction

if TYPE_CHECKING:
    import aiosqlite

    from database.repositories.users.internal_protocols import (
        DatabaseMessagesCoreOwnerProtocol,
    )

__all__ = ("get_conversation_start_snapshot",)


async def get_conversation_start_snapshot(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
    *,
    before_timestamp_exclusive: int,
    counting_mode: Literal["canonical", "including_comparison_variants"],
) -> ConversationStartSnapshot | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> ConversationStartSnapshot | None:
        async def _transaction(
            transaction_database: aiosqlite.Connection,
        ) -> ConversationStartSnapshot | None:
            if not await conversation_exists_for_user(
                transaction_database,
                conv_id=conv_id,
                user_id=user_id,
            ):
                return None

            latest_row = await query_one_to_dict(
                transaction_database,
                "SELECT created_at_ms FROM webui_messages WHERE conv_id = ? ORDER BY created_at_ms DESC, id DESC LIMIT 1",
                (conv_id,),
            )
            if latest_row is None:
                latest_message_timestamp = None
            else:
                timestamp_value = latest_row.get("created_at_ms")
                if not is_strict_int(timestamp_value):
                    raise ValidationError(
                        "Stored conversation message created_at_ms must be an integer.",
                    )
                latest_message_timestamp = int(timestamp_value)

            message_count = await load_conversation_message_count(
                transaction_database,
                conv_id=conv_id,
                before_timestamp_exclusive=before_timestamp_exclusive,
                counting_mode=counting_mode,
            )

            rows = await query_to_dicts(
                transaction_database,
                "SELECT id, role, message_type, content, created_at_ms, assistant_turn_at_ms, model_variant_index, request_id, model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, generation_latency_ms, finish_reason, thinking_tail_duration_ms FROM webui_messages WHERE conv_id = ? ORDER BY created_at_ms ASC, id ASC",
                (conv_id,),
            )
            persisted_messages = [build_message_payload_from_row(row) for row in rows]

            has_assistant = any(
                message.get("role") == "assistant" for message in persisted_messages
            )
            if has_assistant:
                assistant_events = await query_to_dicts(
                    transaction_database,
                    "SELECT assistant_at_ms, sequence, assistant_revision, event_type, payload_json, created_at_ms FROM webui_assistant_message_events WHERE conv_id = ? ORDER BY assistant_at_ms ASC, sequence ASC, created_at_ms ASC",
                    (conv_id,),
                )
                attach_assistant_event_timeline(persisted_messages, assistant_events)
                tool_rows = await query_to_dicts(
                    transaction_database,
                    "SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? ORDER BY assistant_at_ms ASC, sequence_index ASC, created_at_ms ASC, id ASC",
                    (conv_id,),
                )
                attach_tool_call_projections(persisted_messages, tool_rows)

            canonical_history = await query_canonical_agent_history(
                transaction_database,
                conv_id=conv_id,
                before_timestamp_exclusive=before_timestamp_exclusive,
            )
            return ConversationStartSnapshot(
                message_count=message_count,
                latest_message_timestamp=latest_message_timestamp,
                persisted_messages=persisted_messages,
                canonical_history=canonical_history,
            )

        return await run_user_read_transaction(database, _transaction)

    return await self.core.reader.execute_read(_query)

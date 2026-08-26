"""SoAI - Assistant turn stream-state reads [backend/database/repositories/users/messages_stream_state_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.integers import is_strict_int
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_to_dicts
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.message_row_mapping import (
    attach_assistant_event_timeline,
    build_message_payload_from_row,
)
from database.repositories.users.message_tool_projection_attachment import (
    attach_tool_call_projections,
)

if TYPE_CHECKING:
    from database.repositories.users.internal_protocols import (
        DatabaseMessagesCoreOwnerProtocol,
    )

__all__ = ("get_assistant_turn_variant_stream_state",)


async def get_assistant_turn_variant_stream_state(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(
        database: aiosqlite.Connection,
    ) -> (
        tuple[
            JSONDict | None,
            list[dict[str, int | float | str | bytes | None]],
            list[dict[str, int | float | str | bytes | None]],
        ]
        | None
    ):
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None

        message_rows = await query_to_dicts(
            database,
            "SELECT id, role, message_type, content, created_at_ms, assistant_turn_at_ms, model_variant_index, request_id, model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, generation_latency_ms, finish_reason, thinking_tail_duration_ms FROM webui_messages WHERE conv_id = ? AND assistant_turn_at_ms = ? AND model_variant_index = ? AND role = 'assistant' ORDER BY id DESC LIMIT 2",
            (conv_id, assistant_turn_at_ms, model_variant_index),
        )
        if not message_rows:
            return (None, [], [])
        if len(message_rows) != 1:
            raise ValidationError(
                "Stored assistant stream state is invalid: multiple assistant rows exist for the same assistant_turn_at_ms and model_variant_index.",
            )
        message_payload = build_message_payload_from_row(message_rows[0])
        assistant_at_ms_value = message_rows[0].get("created_at_ms")
        if not is_strict_int(assistant_at_ms_value):
            raise ValidationError("Stored assistant message created_at_ms must be an integer.")
        assistant_at_ms = int(assistant_at_ms_value)

        assistant_events = await query_to_dicts(
            database,
            "SELECT assistant_at_ms, sequence, assistant_revision, event_type, payload_json, created_at_ms FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms = ? ORDER BY sequence ASC",
            (conv_id, assistant_at_ms),
        )
        tool_rows = await query_to_dicts(
            database,
            "SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? AND assistant_at_ms = ? ORDER BY sequence_index ASC",
            (conv_id, assistant_at_ms),
        )
        return (message_payload, assistant_events, tool_rows)

    result = await self.core.reader.execute_read(_query)
    if result is None:
        return None
    message_payload, assistant_events, tool_rows = result
    if message_payload is None:
        return None
    messages: list[JSONDict] = [message_payload]
    attach_assistant_event_timeline(messages, assistant_events)
    attach_tool_call_projections(messages, tool_rows)
    return messages[0]

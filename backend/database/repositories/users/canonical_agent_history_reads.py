"""SoAI - Canonical agent-history row loading [backend/database/repositories/users/canonical_agent_history_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.types.json import JSONDict
from database.core.query_execution import query_to_dicts
from database.repositories.users.agent_history import build_canonical_agent_history
from database.repositories.users.conversation_query_filters import (
    build_before_timestamp_exclusive_filter,
)
from database.repositories.users.tool_call_row_mapping import format_tool_call_row

__all__ = ("query_canonical_agent_history",)


async def query_canonical_agent_history(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    before_timestamp_exclusive: int | None,
) -> list[JSONDict]:
    where_before, before_params = build_before_timestamp_exclusive_filter(
        before_timestamp_exclusive,
    )
    tool_where_before, tool_before_params = build_before_timestamp_exclusive_filter(
        before_timestamp_exclusive,
        column="assistant_turn_at_ms",
    )
    event_where_before, event_before_params = build_before_timestamp_exclusive_filter(
        before_timestamp_exclusive,
        column="assistant_at_ms",
    )
    history_params: list[int | str] = [conv_id, *before_params]
    history_message_rows = await query_to_dicts(
        database,
        f"SELECT id, role, message_type, content, created_at_ms, assistant_turn_at_ms, model_variant_index, request_id, model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, generation_latency_ms, finish_reason, thinking_tail_duration_ms FROM webui_messages WHERE conv_id = ? AND message_type = 'chat' AND (role != 'assistant' OR model_variant_index = 0){where_before} ORDER BY created_at_ms ASC, id ASC",
        tuple(history_params),
    )
    tool_call_rows_raw = await query_to_dicts(
        database,
        f"SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? AND model_variant_index = 0{tool_where_before} ORDER BY assistant_at_ms IS NULL ASC, assistant_at_ms ASC, message_index ASC, sequence_index ASC, created_at_ms ASC, id ASC",
        (conv_id, *tool_before_params),
    )
    tool_call_rows = [
        formatted for row in tool_call_rows_raw if (formatted := format_tool_call_row(row))
    ]
    compaction_event_rows = await query_to_dicts(
        database,
        f"SELECT assistant_at_ms, sequence, assistant_revision, event_type, payload_json FROM webui_assistant_message_events WHERE conv_id = ? AND event_type IN ('tool_call_completed', 'assistant_text_delta') AND assistant_at_ms IN (SELECT DISTINCT assistant_at_ms FROM webui_chat_tool_calls WHERE conv_id = ? AND model_variant_index = 0 AND assistant_at_ms IS NOT NULL AND tool_name = ? {tool_where_before}) {event_where_before} ORDER BY assistant_at_ms ASC, sequence ASC, assistant_revision ASC",
        (
            conv_id,
            conv_id,
            CONTEXT_COMPACTION_TOOL_NAME,
            *tool_before_params,
            *event_before_params,
        ),
    )
    history = build_canonical_agent_history(
        message_rows=history_message_rows,
        tool_call_rows=tool_call_rows,
        compaction_event_rows=compaction_event_rows,
    )
    return history

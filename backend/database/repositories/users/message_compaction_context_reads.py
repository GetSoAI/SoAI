"""SoAI - Bounded compaction conversation message reads [backend/database/repositories/users/message_compaction_context_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import ValidationError
from core.tool_calls.context_compaction_markers import (
    extract_context_compaction_marker_from_message,
    is_context_compaction_completed_marker,
)
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_one_to_dict
from database.core.sqlite_values import SQLiteValue
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.internal_protocols import (
    DatabaseMessagesCoreOwnerProtocol,
)
from database.repositories.users.message_row_mapping import build_message_payload_from_row

__all__ = (
    "get_context_compaction_tool_call_id_method",
    "resolve_manual_compaction_message_index_method",
)

_MESSAGE_COLUMNS = (
    "id, role, message_type, content, created_at_ms, assistant_turn_at_ms, model_variant_index, "
    "request_id, model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, "
    "generation_latency_ms, finish_reason, thinking_tail_duration_ms"
)


async def _resolve_target_canonical_assistant_id(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
) -> int:
    row = await query_one_to_dict(
        database,
        """
        SELECT id
        FROM webui_messages
        WHERE conv_id = ?
          AND role = 'assistant'
          AND created_at_ms = ?
          AND assistant_turn_at_ms = created_at_ms
          AND model_variant_index = 0
        ORDER BY id ASC
        LIMIT 1
        """,
        (conv_id, assistant_at_ms),
    )
    if row is None:
        raise ValidationError("Compaction assistant message target could not be resolved.")
    message_id = row.get("id")
    if not is_strict_int(message_id) or message_id < 0:
        raise ValidationError("Compaction assistant message id is invalid.")
    return int(message_id)


async def _count_logical_messages(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    before_created_at_ms: int | None,
    before_id: int | None,
) -> int:
    before_sql = ""
    params: list[SQLiteValue] = [conv_id]
    if before_created_at_ms is not None and before_id is not None:
        before_sql = " AND (created_at_ms < ? OR (created_at_ms = ? AND id < ?))"
        params.extend([before_created_at_ms, before_created_at_ms, before_id])
    row = await query_one_to_dict(
        database,
        f"""
        SELECT COUNT(*) AS message_index
        FROM webui_messages
        WHERE conv_id = ?
          AND message_type = 'chat'
          AND role != 'system'
          AND (role != 'assistant' OR model_variant_index = 0)
          {before_sql}
        """,
        tuple(params),
    )
    if row is None:
        return 0
    count_value = row.get("message_index")
    if not is_strict_int(count_value) or count_value < 0:
        raise ValidationError("Compaction message index is invalid.")
    return int(count_value)


async def resolve_manual_compaction_message_index_method(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
    *,
    replace_assistant_at_ms: int | None,
) -> int | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> int | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None
        if replace_assistant_at_ms is None:
            return await _count_logical_messages(
                database,
                conv_id=conv_id,
                before_created_at_ms=None,
                before_id=None,
            )
        assistant_at_ms = require_unix_epoch_ms(
            replace_assistant_at_ms,
            error_message="Compaction assistant timestamp must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        assistant_id = await _resolve_target_canonical_assistant_id(
            database,
            conv_id=conv_id,
            assistant_at_ms=assistant_at_ms,
        )
        return await _count_logical_messages(
            database,
            conv_id=conv_id,
            before_created_at_ms=assistant_at_ms,
            before_id=assistant_id,
        )

    return await self.core.reader.execute_read(_query)


async def get_context_compaction_tool_call_id_method(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
    *,
    assistant_turn_at_ms: int,
) -> str | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> str | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None
        assistant_at_ms = require_unix_epoch_ms(
            assistant_turn_at_ms,
            error_message="Compaction assistant timestamp must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        row = await query_one_to_dict(
            database,
            f"""
            SELECT {_MESSAGE_COLUMNS}
            FROM webui_messages
            WHERE conv_id = ?
              AND message_type = 'chat'
              AND role = 'assistant'
              AND created_at_ms = ?
              AND assistant_turn_at_ms = created_at_ms
              AND model_variant_index = 0
            ORDER BY id ASC
            LIMIT 1
            """,
            (conv_id, assistant_at_ms),
        )
        if row is None:
            raise ValidationError("Compaction activity was not found.")
        message = build_message_payload_from_row(row)
        marker = extract_context_compaction_marker_from_message(message)
        if marker is None or not is_context_compaction_completed_marker(marker):
            raise ValidationError("Compaction activity was not found.")
        tool_call_id_value = marker.get("tool_call_id")
        if isinstance(tool_call_id_value, str) and tool_call_id_value.strip():
            return tool_call_id_value.strip()
        raise ValidationError("Compaction activity requires a tool call id.")

    return await self.core.reader.execute_read(_query)

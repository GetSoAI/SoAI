"""SoAI - Bounded compaction conversation message reads [backend/database/repositories/users/message_compaction_context_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_TOOL_NAME,
    is_context_compaction_result_boundary_removed,
)
from core.types.json_value import coerce_json_dict
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

__all__ = (
    "get_context_compaction_tool_call_id_method",
    "resolve_manual_compaction_message_index_method",
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
            """
            SELECT tool.call_id, tool.status, tool.tool_result
            FROM webui_messages AS message
            JOIN webui_chat_tool_calls AS tool
              ON tool.conv_id = message.conv_id
             AND tool.assistant_turn_at_ms = message.assistant_turn_at_ms
             AND tool.model_variant_index = message.model_variant_index
            WHERE message.conv_id = ?
              AND message.message_type = 'chat'
              AND message.role = 'assistant'
              AND message.created_at_ms = ?
              AND message.assistant_turn_at_ms = message.created_at_ms
              AND message.model_variant_index = 0
              AND message.finalized_at_ms IS NOT NULL
              AND tool.tool_name = ?
              AND tool.status IN ('completed', 'error', 'cancelled')
            ORDER BY tool.sequence_index DESC, tool.id DESC
            LIMIT 1
            """,
            (conv_id, assistant_at_ms, CONTEXT_COMPACTION_TOOL_NAME),
        )
        if row is None:
            raise ValidationError("Compaction activity was not found.")
        result_value = row.get("tool_result")
        if not isinstance(result_value, str) or not result_value.strip():
            raise ValidationError("Compaction activity result is invalid.")
        result = parse_json_dict(result_value, field="context compaction tool result")
        details = coerce_json_dict(result.get("compaction"))
        if details is None or details.get("trigger") != "manual":
            raise ValidationError("Compaction activity is not a manual boundary.")
        if is_context_compaction_result_boundary_removed(result):
            raise ValidationError("Removed context compaction boundaries cannot be regenerated.")
        tool_call_id_value = row.get("call_id")
        if isinstance(tool_call_id_value, str) and tool_call_id_value.strip():
            return tool_call_id_value.strip()
        raise ValidationError("Compaction activity requires a tool call id.")

    return await self.core.reader.execute_read(_query)

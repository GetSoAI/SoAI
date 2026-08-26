"""SoAI - Bounded auto-title conversation message reads [backend/database/repositories/users/message_auto_title_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.tool_calls.context_compaction_markers import (
    extract_context_compaction_marker_from_message,
)
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.internal_protocols import (
    DatabaseMessagesCoreOwnerProtocol,
)
from database.repositories.users.message_row_mapping import build_message_payload_from_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_auto_title_seed_messages_method",)

_MESSAGE_COLUMNS = (
    "id, role, message_type, content, created_at_ms, assistant_turn_at_ms, model_variant_index, "
    "request_id, model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, "
    "generation_latency_ms, finish_reason, thinking_tail_duration_ms"
)
_ASSISTANT_PAGE_SIZE = 100


def _is_context_compaction_activity_message(message: JSONDict) -> bool:
    if message.get("role") != "assistant":
        return False
    return extract_context_compaction_marker_from_message(message) is not None


async def _load_first_user_message(
    database: aiosqlite.Connection,
    conv_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        f"SELECT {_MESSAGE_COLUMNS} FROM webui_messages WHERE conv_id = ? AND message_type = 'chat' AND role = 'user' ORDER BY created_at_ms ASC, id ASC LIMIT 1",
        (conv_id,),
    )
    return None if row is None else build_message_payload_from_row(row)


def _resolve_cursor(message: JSONDict) -> tuple[int, int]:
    timestamp = require_unix_epoch_ms(
        message.get("timestamp"),
        error_message="Conversation message timestamp must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    message_id = message.get("id")
    if not is_strict_int(message_id) or message_id < 0:
        raise ValidationError("Conversation message id must be a non-negative integer.")
    return (timestamp, int(message_id))


async def _load_first_title_assistant_message(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_message: JSONDict,
) -> JSONDict | None:
    cursor_created_at_ms, cursor_id = _resolve_cursor(user_message)
    while True:
        rows = await query_to_dicts(
            database,
            f"""
            SELECT {_MESSAGE_COLUMNS}
            FROM webui_messages
            WHERE conv_id = ?
              AND message_type = 'chat'
              AND role = 'assistant'
              AND model_variant_index = 0
              AND (created_at_ms > ? OR (created_at_ms = ? AND id > ?))
            ORDER BY created_at_ms ASC, id ASC
            LIMIT ?
            """,
            (
                conv_id,
                cursor_created_at_ms,
                cursor_created_at_ms,
                cursor_id,
                _ASSISTANT_PAGE_SIZE,
            ),
        )
        if not rows:
            return None
        for row in rows:
            message = build_message_payload_from_row(row)
            cursor_created_at_ms, cursor_id = _resolve_cursor(message)
            if not _is_context_compaction_activity_message(message):
                return message


async def get_auto_title_seed_messages_method(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
) -> tuple[JSONDict | None, JSONDict | None] | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(
        database: aiosqlite.Connection,
    ) -> tuple[JSONDict | None, JSONDict | None] | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None
        first_user_message = await _load_first_user_message(database, conv_id)
        if first_user_message is None:
            return (None, None)
        first_assistant_message = await _load_first_title_assistant_message(
            database,
            conv_id=conv_id,
            user_message=first_user_message,
        )
        return (first_user_message, first_assistant_message)

    return await self.core.reader.execute_read(_query)

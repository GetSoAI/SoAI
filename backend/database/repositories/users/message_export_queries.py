"""SoAI - Cursor-paged conversation message export reads [backend/database/repositories/users/message_export_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_to_dicts
from database.repositories.users.internal_protocols import DatabaseMessagesCoreOwnerProtocol
from database.repositories.users.message_row_mapping import build_message_payload_from_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("iter_conversation_export_messages_method",)

_EXPORT_PAGE_SIZE = 1000
_EXPORT_MAX_PAGE_SIZE = 10000
_MESSAGE_COLUMNS = (
    "m.id, m.role, m.message_type, m.content, m.created_at_ms, m.assistant_turn_at_ms, "
    "m.model_variant_index, m.request_id, m.model_id, m.prompt_tokens, "
    "m.completion_tokens, m.total_tokens, m.usage_source, m.generation_latency_ms, "
    "m.finish_reason, m.thinking_tail_duration_ms"
)


async def _load_export_page(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    last_created_at_ms: int | None,
    last_id: int | None,
    limit: int,
) -> list[JSONDict]:
    cursor_filter = ""
    params: tuple[str | int, ...] = (user_id, conv_id, limit)
    if last_created_at_ms is not None and last_id is not None:
        cursor_filter = "AND (m.created_at_ms > ? OR (m.created_at_ms = ? AND m.id > ?))"
        params = (user_id, conv_id, last_created_at_ms, last_created_at_ms, last_id, limit)
    rows = await query_to_dicts(
        database,
        f"""
        SELECT {_MESSAGE_COLUMNS}
        FROM webui_messages AS m
        INNER JOIN webui_conversations AS c ON c.id = m.conv_id
        WHERE c.user_id = ? AND m.conv_id = ? {cursor_filter}
        ORDER BY m.created_at_ms ASC, m.id ASC
        LIMIT ?
        """,
        params,
    )
    return [build_message_payload_from_row(row) for row in rows]


async def iter_conversation_export_messages_method(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    user_id: int,
    *,
    page_size: int = _EXPORT_PAGE_SIZE,
) -> AsyncIterator[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
    if not is_strict_int(page_size) or page_size < 1 or page_size > _EXPORT_MAX_PAGE_SIZE:
        raise ValidationError("Export page size must be between 1 and 10000.")
    last_created_at_ms: int | None = None
    last_id: int | None = None
    while True:
        page = await self.core.reader.execute_read(
            _load_export_page,
            conv_id,
            user_id,
            last_created_at_ms,
            last_id,
            page_size,
        )
        if not page:
            return
        for message in page:
            yield message
        last_message = page[-1]
        timestamp = last_message.get("timestamp")
        message_id = last_message.get("id")
        if not is_strict_int(timestamp) or not is_strict_int(message_id):
            raise ValidationError("Export message cursor is invalid.")
        last_created_at_ms = timestamp
        last_id = message_id

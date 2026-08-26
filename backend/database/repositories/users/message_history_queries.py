"""SoAI - Conversation history tail and search queries [backend/database/repositories/users/message_history_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.database.protocols import DatabaseReaderProtocol
from core.errors.exceptions import DatabaseError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from core.validation.strict_numbers import require_positive_int_strict
from database.core.query_execution import query_to_dicts
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.message_row_mapping import (
    build_message_payload_from_row,
)

if TYPE_CHECKING:
    from core.conversations.conversation_message_window import ConversationMessageCursor
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "load_tail_messages_for_conversation",
    "search_messages_by_content",
)


def _normalize_roles(roles: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for role in roles:
        candidate = role.strip() if isinstance(role, str) else ""
        if not candidate:
            continue
        if candidate in normalized:
            continue
        normalized.append(candidate)
    if not normalized:
        raise ValidationError("Conversation message roles must be a non-empty list.")
    return tuple(normalized)


async def load_tail_messages_for_conversation(
    reader: DatabaseReaderProtocol,
    *,
    conv_id: str,
    user_id: int,
    before_cursor: ConversationMessageCursor | None,
    limit: int,
    roles: tuple[str, ...],
) -> list[JSONDict] | None:
    normalized_roles = _normalize_roles(roles)
    normalized_limit = int(limit)
    if normalized_limit < 1 or normalized_limit > 500:
        raise ValidationError("limit must be between 1 and 500.")
    cursor_created_at_ms: int | None = None
    cursor_id: int | None = None
    if before_cursor is not None:
        cursor_created_at_ms = require_unix_epoch_ms(
            before_cursor.created_at_ms,
            error_message="before_cursor.created_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        cursor_id = require_positive_int_strict(
            before_cursor.id,
            error_message="before_cursor.id must be a positive integer.",
        )

    async def _query(database: aiosqlite.Connection) -> list[JSONDict] | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None

        role_placeholders = ", ".join(["?"] * len(normalized_roles))
        params: list[SQLiteValue] = [conv_id, *normalized_roles]
        where_before = ""
        if cursor_created_at_ms is not None and cursor_id is not None:
            where_before = " AND (created_at_ms < ? OR (created_at_ms = ? AND id < ?))"
            params.extend(
                [
                    cursor_created_at_ms,
                    cursor_created_at_ms,
                    cursor_id,
                ],
            )
        params.append(int(normalized_limit))
        rows = await query_to_dicts(
            database,
            f"SELECT id, role, message_type, content, created_at_ms, assistant_turn_at_ms, model_variant_index, request_id, model_id, prompt_tokens, completion_tokens, total_tokens, usage_source, generation_latency_ms, finish_reason, thinking_tail_duration_ms FROM webui_messages WHERE conv_id = ? AND role IN ({role_placeholders}) AND (role != 'assistant' OR model_variant_index = 0){where_before} ORDER BY created_at_ms DESC, id DESC LIMIT ?",
            tuple(params),
        )
        return [build_message_payload_from_row(row) for row in rows]

    try:
        return await reader.execute_read(_query)
    except RECOVERABLE_EXCEPTIONS as exception:
        raise DatabaseError(
            "Failed to load tail messages for conversation.",
            details={
                "conv_id": conv_id,
                "user_id": user_id,
                "before_cursor": (
                    None
                    if before_cursor is None
                    else {
                        "created_at_ms": before_cursor.created_at_ms,
                        "id": before_cursor.id,
                    }
                ),
                "limit": normalized_limit,
                "roles": list(normalized_roles),
            },
            operation="database_users.get_messages_tail",
            cause=exception,
        ) from exception


async def search_messages_by_content(
    reader: DatabaseReaderProtocol,
    *,
    user_id: int,
    query: str,
    limit: int,
    include_automation: bool,
    roles: tuple[str, ...],
) -> list[JSONDict]:
    normalized_roles = _normalize_roles(roles)
    normalized_query = query.strip() if isinstance(query, str) else ""
    if not normalized_query:
        raise ValidationError("query must be a non-empty string.")
    normalized_limit = int(limit)
    if normalized_limit < 1 or normalized_limit > 500:
        raise ValidationError("limit must be between 1 and 500.")
    automation_filter_sql = "" if include_automation else " AND c.is_automation = 0"

    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        role_placeholders = ", ".join(["?"] * len(normalized_roles))
        params: list[SQLiteValue] = [
            user_id,
            *normalized_roles,
            normalized_query,
            normalized_limit,
        ]
        rows = await query_to_dicts(
            database,
            f"SELECT c.id AS conv_id, c.title AS title, c.last_modified_at_ms AS last_modified_at_ms, m.id AS id, m.role AS role, m.message_type AS message_type, m.content AS content, m.created_at_ms AS created_at_ms, m.assistant_turn_at_ms AS assistant_turn_at_ms, m.model_variant_index AS model_variant_index, m.request_id AS request_id, m.model_id AS model_id, m.prompt_tokens AS prompt_tokens, m.completion_tokens AS completion_tokens, m.total_tokens AS total_tokens, m.usage_source AS usage_source, m.generation_latency_ms AS generation_latency_ms, m.finish_reason AS finish_reason, m.thinking_tail_duration_ms AS thinking_tail_duration_ms FROM webui_messages m JOIN webui_conversations c ON c.id = m.conv_id WHERE c.user_id = ? AND m.role IN ({role_placeholders}){automation_filter_sql} AND (m.role != 'assistant' OR m.model_variant_index = 0) AND instr(lower(m.content), lower(?)) > 0 ORDER BY m.created_at_ms DESC, m.id DESC LIMIT ?",
            tuple(params),
        )
        results: list[JSONDict] = []
        for row in rows:
            conv_id = row.get("conv_id")
            title = row.get("title")
            last_modified_at = row.get("last_modified_at_ms")
            if not isinstance(conv_id, str) or not conv_id.strip():
                raise StateError("Conversation search result id is invalid.")
            if not isinstance(title, str):
                raise StateError("Conversation search result title is invalid.")
            if not is_strict_int(last_modified_at):
                raise StateError("Conversation search result timestamp is invalid.")
            message_payload = build_message_payload_from_row(row)
            results.append(
                {
                    "conv_id": conv_id,
                    "title": title,
                    "last_modified_at_ms": int(last_modified_at),
                    "message": message_payload,
                },
            )
        return results

    try:
        return await reader.execute_read(_query)
    except RECOVERABLE_EXCEPTIONS as exception:
        raise DatabaseError(
            "Failed to search conversation messages.",
            details={
                "user_id": user_id,
                "query": normalized_query,
                "limit": normalized_limit,
                "include_automation": bool(include_automation),
                "roles": list(normalized_roles),
            },
            operation="database_users.search_messages_by_content",
            cause=exception,
        ) from exception

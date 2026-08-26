"""SoAI - Tool call repository read operations [backend/database/repositories/users/tool_call_read_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.tool_call_identity_queries import (
    build_tool_call_identity_query,
)
from database.repositories.users.tool_call_row_mapping import format_tool_call_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.users.internal_protocols import (
        DatabaseMessagesCoreOwnerProtocol,
    )

__all__ = (
    "get_tool_call_by_identity",
    "get_tool_call_by_storage_id",
    "get_tool_call_for_agent_lineage",
    "get_tool_call_for_assistant_variant",
    "get_tool_calls_for_assistant_turn",
    "get_tool_calls_for_turn",
)


async def get_tool_call_by_storage_id(
    self: DatabaseMessagesCoreOwnerProtocol,
    storage_call_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            "SELECT * FROM webui_chat_tool_calls WHERE id = ? LIMIT 1",
            (storage_call_id,),
        )
        return format_tool_call_row(row)

    return await self.core.reader.execute_read(_query)


async def get_tool_call_for_agent_lineage(
    self: DatabaseMessagesCoreOwnerProtocol,
    *,
    conv_id: str,
    call_id: str,
    turn_id: str,
    iteration_index: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            "SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? AND call_id = ? AND turn_id = ? AND iteration_index = ? AND assistant_turn_at_ms = ? AND model_variant_index = ? ORDER BY created_at_ms DESC, id DESC LIMIT 1",
            (conv_id, call_id, turn_id, iteration_index, assistant_turn_at_ms, model_variant_index),
        )
        return format_tool_call_row(row)

    return await self.core.reader.execute_read(_query)


async def get_tool_call_for_assistant_variant(
    self: DatabaseMessagesCoreOwnerProtocol,
    *,
    conv_id: str,
    call_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            "SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? AND call_id = ? AND assistant_turn_at_ms = ? AND model_variant_index = ? ORDER BY created_at_ms DESC, id DESC LIMIT 1",
            (conv_id, call_id, assistant_turn_at_ms, model_variant_index),
        )
        return format_tool_call_row(row)

    return await self.core.reader.execute_read(_query)


async def get_tool_call_by_identity(
    self: DatabaseMessagesCoreOwnerProtocol,
    *,
    conv_id: str,
    call_id: str,
    turn_id: str | None,
    iteration_index: int | None,
    message_index: int | None,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        query, query_params = build_tool_call_identity_query(
            model_variant_index=model_variant_index,
            assistant_turn_at_ms=assistant_turn_at_ms,
            message_index=message_index,
            iteration_index=iteration_index,
            turn_id=turn_id,
            call_id=call_id,
            conv_id=conv_id,
        )
        row = await query_one_to_dict(database, query, query_params)
        return format_tool_call_row(row)

    return await self.core.reader.execute_read(_query)


async def get_tool_calls_for_assistant_turn(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            "SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? AND assistant_turn_at_ms = ? AND model_variant_index = ? ORDER BY sequence_index ASC, created_at_ms ASC, id ASC",
            (conv_id, assistant_turn_at_ms, model_variant_index),
        )
        return [formatted for row in rows if (formatted := format_tool_call_row(row))]

    return await self.core.reader.execute_read(_query)


async def get_tool_calls_for_turn(
    self: DatabaseMessagesCoreOwnerProtocol,
    conv_id: str,
    turn_id: str,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            "SELECT * FROM webui_chat_tool_calls WHERE conv_id = ? AND turn_id = ? ORDER BY sequence_index ASC, created_at_ms ASC, id ASC",
            (conv_id, turn_id),
        )
        return [formatted for row in rows if (formatted := format_tool_call_row(row))]

    return await self.core.reader.execute_read(_query)

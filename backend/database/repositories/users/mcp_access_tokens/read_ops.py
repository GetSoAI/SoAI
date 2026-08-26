"""SoAI - MCP access token repository read operations [backend/database/repositories/users/mcp_access_tokens/read_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import aiosqlite

from core.database.protocols import DatabaseCoreProtocol
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite
from database.repositories.users.bearer_token_fingerprint_reads import (
    BearerTokenTable,
    read_ordered_bearer_token_row,
)
from database.repositories.users.mcp_access_token_row_normalization import (
    normalize_mcp_access_token_row,
    sanitize_mcp_access_token_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "count_non_revoked_tokens_without_expiration",
    "get_active_token_by_fingerprints",
    "get_token_by_fingerprints",
    "get_token_by_id",
    "list_tokens_for_user",
)


async def count_non_revoked_tokens_without_expiration(core: DatabaseCoreProtocol) -> int:
    async def _query(database: aiosqlite.Connection) -> int:
        rows = await query_to_dicts(
            database,
            "SELECT COUNT(*) AS count FROM mcp_access_tokens WHERE revoked = 0 AND expires_at_ms IS NULL",
        )
        if not rows:
            return 0
        return coerce_non_negative_int_from_sqlite(rows[0].get("count"))

    return await core.reader.execute_read(_query)


async def list_tokens_for_user(
    core: DatabaseCoreProtocol,
    user_id: int,
    *,
    include_revoked: bool,
    decrypt_hash: Callable[[str | None], str | None],
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        if include_revoked:
            query = """
                SELECT tokens.* FROM mcp_access_tokens tokens
                JOIN webui_users users ON users.id = tokens.user_id
                WHERE tokens.user_id = ? AND users.account_type = 'human'
                ORDER BY tokens.created_at_ms DESC
            """
            params = (int(user_id),)
        else:
            query = """
                SELECT tokens.* FROM mcp_access_tokens tokens
                JOIN webui_users users ON users.id = tokens.user_id
                WHERE tokens.user_id = ? AND users.account_type = 'human'
                  AND tokens.revoked = 0
                ORDER BY tokens.created_at_ms DESC
            """
            params = (int(user_id),)
        rows = await query_to_dicts(database, query, params)
        sanitized: list[JSONDict] = []
        for row in rows:
            normalized = normalize_mcp_access_token_row(row, decrypt_hash=decrypt_hash)
            sanitized_row = sanitize_mcp_access_token_row(normalized)
            if sanitized_row is not None:
                sanitized.append(sanitized_row)
        return sanitized

    return await core.reader.execute_read(_query)


async def get_token_by_id(
    core: DatabaseCoreProtocol,
    token_id: str,
    *,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            """
            SELECT tokens.* FROM mcp_access_tokens tokens
            JOIN webui_users users ON users.id = tokens.user_id
            WHERE tokens.token_id = ? AND users.account_type = 'human'
            """,
            (token_id,),
        )
        return normalize_mcp_access_token_row(row, decrypt_hash=decrypt_hash)

    return await core.reader.execute_read(_query)


async def get_token_by_fingerprints(
    core: DatabaseCoreProtocol,
    fingerprints: tuple[str, ...],
    *,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    row = await read_ordered_bearer_token_row(
        core,
        BearerTokenTable.MCP_ACCESS_TOKENS,
        fingerprints,
        active_at_ms=None,
    )
    return normalize_mcp_access_token_row(row, decrypt_hash=decrypt_hash)


async def get_active_token_by_fingerprints(
    core: DatabaseCoreProtocol,
    fingerprints: tuple[str, ...],
    *,
    now_ms: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    row = await read_ordered_bearer_token_row(
        core,
        BearerTokenTable.MCP_ACCESS_TOKENS,
        fingerprints,
        active_at_ms=now_ms,
    )
    return normalize_mcp_access_token_row(row, decrypt_hash=decrypt_hash)

"""SoAI - Ordered bearer-token fingerprint reads [backend/database/repositories/users/bearer_token_fingerprint_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import aiosqlite

from core.database.protocols import DatabaseCoreProtocol
from database.core.query_execution import query_to_dicts

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict, SQLiteValue

__all__ = ("BearerTokenTable", "read_ordered_bearer_token_row")


class BearerTokenTable(Enum):
    OPENAI_API_KEYS = 1
    MCP_ACCESS_TOKENS = 2


async def read_ordered_bearer_token_row(
    core: DatabaseCoreProtocol,
    table: BearerTokenTable,
    fingerprints: tuple[str, ...],
    *,
    active_at_ms: int | None,
) -> SQLiteRowDict | None:
    if not fingerprints:
        return None

    async def _query(database: aiosqlite.Connection) -> SQLiteRowDict | None:
        placeholders = ", ".join("?" for _fingerprint in fingerprints)
        if table is BearerTokenTable.OPENAI_API_KEYS:
            query = f"SELECT * FROM openai_api_keys WHERE fingerprint IN ({placeholders})"
        else:
            query = (
                "SELECT tokens.* FROM mcp_access_tokens tokens "
                "JOIN webui_users users ON users.id = tokens.user_id "
                f"WHERE tokens.fingerprint IN ({placeholders}) "
                "AND users.account_type = 'human'"
            )
        parameters: tuple[SQLiteValue, ...]
        if active_at_ms is None:
            parameters = fingerprints
        else:
            query = f"{query} AND revoked = 0 AND (expires_at_ms IS NULL OR expires_at_ms > ?)"
            parameters = (*fingerprints, int(active_at_ms))
        rows = await query_to_dicts(database, query, parameters)
        rows_by_fingerprint = {row.get("fingerprint"): row for row in rows}
        for fingerprint in fingerprints:
            row = rows_by_fingerprint.get(fingerprint)
            if row is not None:
                return row
        return None

    return await core.reader.execute_read(_query)

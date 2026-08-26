"""SoAI - OpenAI API key repository read operations [backend/database/repositories/users/api_keys/read_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import aiosqlite

from core.database.protocols import DatabaseCoreProtocol
from core.timing.epoch import epoch_ms
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite
from database.repositories.users.api_key_row_normalization import (
    normalize_api_key_row,
    sanitize_api_key_row,
)
from database.repositories.users.bearer_token_fingerprint_reads import (
    BearerTokenTable,
    read_ordered_bearer_token_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "count_active_keys",
    "count_non_revoked_keys_without_expiration",
    "get_active_key_by_fingerprints",
    "get_key_by_fingerprints",
    "get_key_by_id",
    "has_any_active_key",
    "count_configured_keys",
    "list_keys",
)


async def count_active_keys(core: DatabaseCoreProtocol, *, now_ms: int) -> int:
    async def _query(database: aiosqlite.Connection) -> int:
        rows = await query_to_dicts(
            database,
            "SELECT COUNT(*) AS count FROM openai_api_keys WHERE revoked = 0 AND (expires_at_ms IS NULL OR expires_at_ms > ?)",
            (int(now_ms),),
        )
        if not rows:
            return 0
        count_value = rows[0].get("count")
        return coerce_non_negative_int_from_sqlite(count_value)

    return await core.reader.execute_read(_query)


async def count_non_revoked_keys_without_expiration(core: DatabaseCoreProtocol) -> int:
    async def _query(database: aiosqlite.Connection) -> int:
        rows = await query_to_dicts(
            database,
            "SELECT COUNT(*) AS count FROM openai_api_keys WHERE revoked = 0 AND expires_at_ms IS NULL",
        )
        if not rows:
            return 0
        return coerce_non_negative_int_from_sqlite(rows[0].get("count"))

    return await core.reader.execute_read(_query)


async def has_any_active_key(core: DatabaseCoreProtocol, *, now_ms: int) -> bool:
    async def _query(database: aiosqlite.Connection) -> bool:
        rows = await query_to_dicts(
            database,
            "SELECT 1 AS value FROM openai_api_keys WHERE revoked = 0 AND (expires_at_ms IS NULL OR expires_at_ms > ?) LIMIT 1",
            (int(now_ms),),
        )
        return bool(rows)

    return await core.reader.execute_read(_query)


async def count_configured_keys(core: DatabaseCoreProtocol) -> int:
    async def _query(database: aiosqlite.Connection) -> int:
        rows = await query_to_dicts(
            database,
            "SELECT COUNT(*) AS count FROM openai_api_keys",
        )
        if not rows:
            return 0
        return coerce_non_negative_int_from_sqlite(rows[0].get("count"))

    return await core.reader.execute_read(_query)


async def list_keys(
    core: DatabaseCoreProtocol,
    *,
    include_revoked: bool,
    decrypt_hash: Callable[[str | None], str | None],
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        query = (
            "SELECT * FROM openai_api_keys ORDER BY created_at_ms DESC"
            if include_revoked
            else "SELECT * FROM openai_api_keys WHERE revoked = 0 ORDER BY created_at_ms DESC"
        )
        rows = await query_to_dicts(database, query)
        sanitized: list[JSONDict] = []
        now_ts = epoch_ms()
        for row in rows:
            normalized = normalize_api_key_row(row, now_ts=now_ts, decrypt_hash=decrypt_hash)
            sanitized_row = sanitize_api_key_row(normalized)
            if sanitized_row:
                sanitized.append(sanitized_row)
        return sanitized

    return await core.reader.execute_read(_query)


async def get_key_by_id(
    core: DatabaseCoreProtocol,
    key_id: str,
    *,
    now_ms: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            "SELECT * FROM openai_api_keys WHERE key_id = ?",
            (key_id,),
        )
        return normalize_api_key_row(row, now_ts=int(now_ms), decrypt_hash=decrypt_hash)

    return await core.reader.execute_read(_query)


async def get_key_by_fingerprints(
    core: DatabaseCoreProtocol,
    fingerprints: tuple[str, ...],
    *,
    now_ms: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    row = await read_ordered_bearer_token_row(
        core,
        BearerTokenTable.OPENAI_API_KEYS,
        fingerprints,
        active_at_ms=None,
    )
    return normalize_api_key_row(
        row,
        now_ts=int(now_ms),
        decrypt_hash=decrypt_hash,
    )


async def get_active_key_by_fingerprints(
    core: DatabaseCoreProtocol,
    fingerprints: tuple[str, ...],
    *,
    now_ms: int,
    decrypt_hash: Callable[[str | None], str | None],
) -> JSONDict | None:
    row = await read_ordered_bearer_token_row(
        core,
        BearerTokenTable.OPENAI_API_KEYS,
        fingerprints,
        active_at_ms=now_ms,
    )
    return normalize_api_key_row(
        row,
        now_ts=int(now_ms),
        decrypt_hash=decrypt_hash,
    )

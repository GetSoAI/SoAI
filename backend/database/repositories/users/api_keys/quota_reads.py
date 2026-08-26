"""SoAI - OpenAI API key quota config read operations [backend/database/repositories/users/api_keys/quota_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.database.protocols import DatabaseCoreProtocol
from database.core.query_execution import query_one_to_dict
from database.repositories.users.api_key_quota_config import normalize_quota_config_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_quota_config",)


async def get_quota_config(core: DatabaseCoreProtocol, key_id: str) -> JSONDict:
    async def _query(database: aiosqlite.Connection) -> JSONDict:
        row = await query_one_to_dict(
            database,
            "SELECT * FROM openai_api_key_quota_config WHERE key_id = ?",
            (key_id,),
        )
        return normalize_quota_config_row(row)

    return await core.reader.execute_read(_query)

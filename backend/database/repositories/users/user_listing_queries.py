"""SoAI - Human and internal account listing queries [backend/database/repositories/users/user_listing_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.types.json import JSONDict
from core.users.account_types import HUMAN_ACCOUNT_TYPE
from database.core.query_execution import query_to_dicts
from database.repositories.users.user_row_normalization import normalize_user_row


async def query_human_users(database: aiosqlite.Connection) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        "SELECT * FROM webui_users WHERE account_type = ? ORDER BY username",
        (HUMAN_ACCOUNT_TYPE,),
    )
    return [normalized for row in rows if row and (normalized := normalize_user_row(row))]


async def query_all_accounts(database: aiosqlite.Connection) -> list[JSONDict]:
    rows = await query_to_dicts(database, "SELECT * FROM webui_users ORDER BY id")
    return [normalized for row in rows if (normalized := normalize_user_row(row))]


__all__ = ("query_all_accounts", "query_human_users")

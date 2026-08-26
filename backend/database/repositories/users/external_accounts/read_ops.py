"""SoAI - External account repository read operations [backend/database/repositories/users/external_accounts/read_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.users.account_identifier_validation import require_external_account_id
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.external_accounts.validation import require_user_id

__all__ = (
    "read_external_account",
    "read_external_accounts",
)


async def read_external_accounts(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT *
        FROM external_accounts
        WHERE user_id = ?
        ORDER BY created_at_ms DESC, id DESC
        """,
        (require_user_id(user_id),),
    )


async def read_external_account(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    external_account_id: str,
) -> SQLiteRowDict | None:
    normalized_account_id = require_external_account_id(external_account_id)
    return await query_one_to_dict(
        database,
        """
        SELECT *
        FROM external_accounts
        WHERE user_id = ? AND id = ?
        LIMIT 1
        """,
        (require_user_id(user_id), normalized_account_id),
    )

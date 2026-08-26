"""SoAI - User repository read transaction helpers [backend/database/repositories/users/read_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

import aiosqlite

from core.sqlite.aiosqlite_cleanup import wait_for_aiosqlite_cleanup

__all__ = ("run_user_read_transaction",)


async def run_user_read_transaction[ReadResultT](
    database: aiosqlite.Connection,
    query: Callable[[aiosqlite.Connection], Awaitable[ReadResultT]],
) -> ReadResultT:
    committed = False
    await database.execute("BEGIN")
    try:
        result = await query(database)
        await database.execute("COMMIT")
        committed = True
        return result
    finally:
        if not committed:
            await wait_for_aiosqlite_cleanup(database.execute("ROLLBACK"))

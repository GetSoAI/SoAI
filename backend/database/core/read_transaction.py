"""SoAI - Shared SQLite read snapshot transaction [backend/database/core/read_transaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

import aiosqlite

from core.sqlite.aiosqlite_cleanup import wait_for_aiosqlite_cleanup

__all__ = ("run_read_transaction",)


async def run_read_transaction[ReadResultT](
    database: aiosqlite.Connection,
    query: Callable[[aiosqlite.Connection], Awaitable[ReadResultT]],
) -> ReadResultT:
    try:
        await database.execute("BEGIN")
        return await query(database)
    finally:
        await wait_for_aiosqlite_cleanup(database.execute("ROLLBACK"))

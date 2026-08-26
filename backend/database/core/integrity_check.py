"""SoAI - Database integrity verification after process recovery [backend/database/core/integrity_check.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.protocols import DatabaseReaderProtocol
from core.errors.exceptions import DatabaseError
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    import aiosqlite

__all__ = ("verify_database_after_unclean_shutdown",)

OPERATION = "database.core.integrity_check.verify_after_unclean_shutdown"


async def _run_quick_check(connection: aiosqlite.Connection) -> tuple[str, ...]:
    cursor = await connection.execute("PRAGMA quick_check")
    try:
        rows = await cursor.fetchall()
    finally:
        await cursor.close()
    return tuple(row[0] for row in rows if row and isinstance(row[0], str))


async def verify_database_after_unclean_shutdown(
    reader: DatabaseReaderProtocol,
    logger: LoggerProtocol,
) -> None:
    results = await reader.execute_read(_run_quick_check)
    if results != ("ok",):
        logger.critical(
            "Database integrity verification failed after an unclean shutdown. SoAI will not modify the damaged database automatically. Stop SoAI, preserve a copy of the database and its WAL/SHM files, then restore a known-good SoAI backup. If no backup is usable, run the SQLite CLI .recover command into a separate database file and validate that recovered copy before replacing the original. SQLite recovery can omit or alter damaged data and may cause permanent data loss. Before returning the recovered database to service, check the host for unstable hardware or overclocking, faulty RAM, and storage device or filesystem errors that could have caused the corruption.",
        )
        raise DatabaseError(
            "Database integrity verification failed after an unclean SoAI shutdown.",
            details={"quick_check_results": list(results)},
            operation=OPERATION,
        )

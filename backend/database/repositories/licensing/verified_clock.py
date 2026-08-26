"""SoAI - Licensing verified-time high-water persistence [backend/database/repositories/licensing/verified_clock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.errors.exceptions import DatabaseError
from core.validation.epoch import require_unix_epoch_ms


async def read_verified_time_high_water_query(
    connection: aiosqlite.Connection,
) -> int | None:
    cursor = await connection.execute(
        "SELECT verified_time_high_water_ms FROM licensing_verified_clock WHERE singleton = 1"
    )
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        return None
    return require_unix_epoch_ms(
        row[0],
        error_message="Persisted licensing verified time is invalid.",
    )


def sync_advance_verified_time(
    connection: sqlite3.Connection,
    verified_time_ms: int,
) -> int:
    validated_time = require_unix_epoch_ms(
        verified_time_ms,
        error_message="Licensing verified time must be a valid epoch-millisecond integer.",
    )
    connection.execute(
        """INSERT INTO licensing_verified_clock (singleton, verified_time_high_water_ms)
        VALUES (1, ?)
        ON CONFLICT(singleton) DO UPDATE SET verified_time_high_water_ms =
            MAX(verified_time_high_water_ms, excluded.verified_time_high_water_ms)""",
        (validated_time,),
    )
    row = connection.execute(
        "SELECT verified_time_high_water_ms FROM licensing_verified_clock WHERE singleton = 1"
    ).fetchone()
    if row is None:
        raise DatabaseError("Licensing verified-time high-water persistence failed.")
    return int(row[0])


__all__ = ("read_verified_time_high_water_query", "sync_advance_verified_time")

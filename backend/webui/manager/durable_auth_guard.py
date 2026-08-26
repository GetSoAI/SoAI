"""SoAI - Durable auth failure guard backed by SQLite [backend/webui/manager/durable_auth_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.database.protocols import DatabaseCoreProtocol
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    import aiosqlite

__all__ = ("DurableAuthFailureGuard",)


class DurableAuthFailureGuard:
    def __init__(
        self,
        database_core: DatabaseCoreProtocol,
        *,
        window_seconds: int,
        max_failures: int,
        max_entries: int = 10000,
    ) -> None:
        self._core = database_core
        self.window_ms = max(int(window_seconds) or 1, 1) * 1000
        self.max_failures = max(int(max_failures) or 1, 1)
        self._max_entries = max(int(max_entries) or 1000, 1000)

    def _identifier_bucket(self, identifier: str) -> str:
        return identifier or "unknown"

    def _count_is_throttled(self, count: int) -> bool:
        return int(count) >= int(self.max_failures)

    async def _read_bucket(
        self,
        database: aiosqlite.Connection,
        identifier: str,
    ) -> tuple[int, int] | None:
        cursor = await database.execute(
            "SELECT count, window_start_at_ms FROM auth_failure_buckets WHERE bucket_id = ?",
            (identifier,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return None
        count_raw, window_raw = row
        return (int(count_raw), int(window_raw))

    def _sync_delete_bucket(self, conn: sqlite3.Connection, identifier: str) -> None:
        conn.execute("DELETE FROM auth_failure_buckets WHERE bucket_id = ?", (identifier,))

    def _sync_delete_bucket_if_window_matches(
        self,
        conn: sqlite3.Connection,
        identifier: str,
        window_start_at_ms: int,
    ) -> None:
        conn.execute(
            "DELETE FROM auth_failure_buckets WHERE bucket_id = ? AND window_start_at_ms = ?",
            (identifier, int(window_start_at_ms)),
        )

    def _sync_prune_expired(self, conn: sqlite3.Connection, cutoff_window_start: int) -> None:
        conn.execute(
            "DELETE FROM auth_failure_buckets WHERE window_start_at_ms <= ?",
            (int(cutoff_window_start),),
        )

    def _sync_prune_oldest_if_needed(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("SELECT COUNT(*) FROM auth_failure_buckets")
        row = cursor.fetchone()
        total = int(row[0]) if row else 0
        if total <= self._max_entries:
            return
        to_delete = total - self._max_entries
        conn.execute(
            """
            DELETE FROM auth_failure_buckets
            WHERE bucket_id IN (
                SELECT bucket_id
                FROM auth_failure_buckets
                ORDER BY updated_at_ms ASC
                LIMIT ?
            )
            """,
            (int(to_delete),),
        )

    def _sync_register_failure(self, conn: sqlite3.Connection, identifier: str) -> tuple[int, int]:
        now = int(epoch_ms())
        cursor = conn.execute(
            "SELECT count, window_start_at_ms FROM auth_failure_buckets WHERE bucket_id = ?",
            (identifier,),
        )
        row = cursor.fetchone()
        if not row:
            count = 1
            window_start_at_ms = now
        else:
            existing_count, existing_window_start_at_ms = int(row[0]), int(row[1])
            if now >= existing_window_start_at_ms + self.window_ms:
                count = 1
                window_start_at_ms = now
            else:
                count = existing_count + 1
                window_start_at_ms = existing_window_start_at_ms
        conn.execute(
            """
            INSERT INTO auth_failure_buckets (bucket_id, count, window_start_at_ms, updated_at_ms)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bucket_id) DO UPDATE SET
                count=excluded.count,
                window_start_at_ms=excluded.window_start_at_ms,
                updated_at_ms=excluded.updated_at_ms
            """,
            (identifier, int(count), int(window_start_at_ms), int(now)),
        )
        cutoff_window_start = now - self.window_ms
        self._sync_prune_expired(conn, cutoff_window_start)
        self._sync_prune_oldest_if_needed(conn)
        return (int(count), int(window_start_at_ms))

    async def is_throttled(self, identifier: str) -> tuple[bool, int | None]:
        identifier_value = self._identifier_bucket(identifier)
        now = int(epoch_ms())
        record = await self._core.reader.execute_read(self._read_bucket, identifier_value)
        if not record:
            return (False, None)
        count, window_start_at_ms = record
        if now >= window_start_at_ms + self.window_ms:
            await self._core.writer.queue_write_operation(
                self._sync_delete_bucket_if_window_matches,
                identifier_value,
                int(window_start_at_ms),
            )
            return (False, None)
        if self._count_is_throttled(count):
            return (True, window_start_at_ms + self.window_ms)
        return (False, None)

    async def register_failure(self, identifier: str) -> tuple[bool, int | None]:
        identifier_value = self._identifier_bucket(identifier)
        count, window_start_at_ms = await self._core.writer.queue_write_operation(
            self._sync_register_failure,
            identifier_value,
        )
        if self._count_is_throttled(count):
            return (True, window_start_at_ms + self.window_ms)
        return (False, None)

    async def reset(self, identifier: str) -> None:
        identifier_value = self._identifier_bucket(identifier)
        await self._core.writer.queue_write_operation(
            self._sync_delete_bucket,
            identifier_value,
        )

"""SoAI - Database read connection pool [backend/database/io/read_pool.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time

import aiosqlite

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ConfigurationError, DatabaseError
from core.logging.trace import get_logger
from core.sqlite.policy import (
    configure_aiosqlite_connection,
    resolve_sqlite_database_target,
)
from core.state.errors import DatabaseUnavailableError
from core.timing.constants import CONTROL_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC

__all__ = ("ReadConnectionPool",)

LOGGER_NAME = "SoAI.database.io.read_pool"
OPERATION_CLOSE_CONNECTION = "database.io.read_pool.close_connection"
OPERATION_INTERRUPT_CONNECTION = "database.io.read_pool.interrupt_connection"
OPERATION_SHUTDOWN = "database.io.read_pool.shutdown"


class ReadConnectionPool:
    def __init__(
        self,
        db_path: str,
        *,
        is_shared_memory_mode: bool,
        pragmas: tuple[str, ...],
        connect_timeout: float = 10.0,
        max_pool_size: int = 4,
        max_idle_time_sec: float = 300.0,
        health_check_idle_threshold_sec: float = 30.0,
    ) -> None:
        self._db_path = db_path
        self._is_shared_memory_mode = is_shared_memory_mode
        self._pragmas = pragmas
        self._connect_timeout = connect_timeout
        self._max_idle_time_sec = max_idle_time_sec
        self._health_check_idle_threshold_sec = health_check_idle_threshold_sec
        self._pool: asyncio.Queue[tuple[aiosqlite.Connection, float]] = asyncio.Queue(
            maxsize=max_pool_size,
        )
        self._active_semaphore = asyncio.Semaphore(max_pool_size)
        self._shutdown = False
        self._borrowed_connections: set[aiosqlite.Connection] = set()
        self._borrowed_connections_drained = asyncio.Event()
        self._borrowed_connections_drained.set()
        self._state_lock = asyncio.Lock()

    async def _create_connection(self) -> aiosqlite.Connection:
        database_target, use_uri = resolve_sqlite_database_target(
            self._db_path,
            is_shared_memory_mode=self._is_shared_memory_mode,
            read_only=True,
        )
        connection = await aiosqlite.connect(
            database_target,
            timeout=self._connect_timeout,
            uri=use_uri,
        )

        try:
            await configure_aiosqlite_connection(connection, self._pragmas)
        except asyncio.CancelledError:
            await self._close_connection_safe(connection)
            raise
        except (
            aiosqlite.Error,
            ConfigurationError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
        ):
            await self._close_connection_safe(connection)
            raise
        return connection

    async def acquire(self) -> aiosqlite.Connection:
        if self._shutdown:
            raise DatabaseUnavailableError("Read pool is shut down.")
        await self._active_semaphore.acquire()
        if self._shutdown:
            self._active_semaphore.release()
            raise DatabaseUnavailableError("Read pool is shut down.")
        connection: aiosqlite.Connection | None = None
        semaphore_released = False
        connection_registered = False
        connection_acquired = False
        try:
            connection = await self._acquire_connection_internal()
            should_close = False
            async with self._state_lock:
                if self._shutdown:
                    should_close = True
                else:
                    self._borrowed_connections.add(connection)
                    self._borrowed_connections_drained.clear()
                    connection_registered = True
            if should_close:
                await self._close_connection_safe(connection)
                raise DatabaseUnavailableError("Read pool is shut down.")
            connection_acquired = True
            return connection
        except asyncio.CancelledError:
            if connection is not None and not connection_acquired:
                if connection_registered:
                    await uncancel_then_cleanup(self.release(connection))
                    semaphore_released = True
                else:
                    await uncancel_then_cleanup(self._close_connection_safe(connection))
            raise
        finally:
            if not connection_acquired and not semaphore_released:
                self._active_semaphore.release()

    async def _acquire_connection_internal(self) -> aiosqlite.Connection:
        now = time.monotonic()
        while True:
            try:
                connection, released_at = self._pool.get_nowait()
                idle_seconds = now - released_at
                if idle_seconds > self._max_idle_time_sec:
                    await self._close_connection_safe(connection)
                    continue
                if idle_seconds <= self._health_check_idle_threshold_sec:
                    return connection
                try:
                    await self._check_connection_health(connection)
                    return connection
                except asyncio.CancelledError:
                    await self._close_connection_safe(connection)
                    raise
                except aiosqlite.Error:
                    await self._close_connection_safe(connection)
                    continue
            except asyncio.QueueEmpty:
                break
        return await self._create_connection()

    @staticmethod
    async def _check_connection_health(connection: aiosqlite.Connection) -> None:
        async with connection.execute("SELECT 1") as cursor:
            await cursor.fetchone()

    async def release(self, connection: aiosqlite.Connection) -> None:
        await uncancel_then_cleanup(self._release_connection_internal(connection))

    async def _release_connection_internal(self, connection: aiosqlite.Connection) -> None:
        try:
            should_close = False
            async with self._state_lock:
                self._borrowed_connections.discard(connection)
                if not self._borrowed_connections:
                    self._borrowed_connections_drained.set()
                if self._shutdown:
                    should_close = True
                else:
                    try:
                        self._pool.put_nowait((connection, time.monotonic()))
                    except asyncio.QueueFull:
                        should_close = True
            if should_close:
                await self._close_connection_safe(connection)
        finally:
            self._active_semaphore.release()

    @staticmethod
    async def _close_connection_safe(connection: aiosqlite.Connection) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            await connection.close()
        except (
            aiosqlite.Error,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
        ) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to close SQLite connection.",
                operation=OPERATION_CLOSE_CONNECTION,
                level="debug",
            )

    async def _wait_for_borrowed_drain(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(
                self._borrowed_connections_drained.wait(),
                timeout=timeout,
            )
        except TimeoutError:
            return False
        return True

    async def _interrupt_borrowed_connections(self) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._state_lock:
            borrowed_connections = tuple(self._borrowed_connections)
        logger.warning(
            "Read pool shutdown timed out after %.1fs while waiting for %d borrowed connection(s).",
            CONTROL_TIMEOUT_SEC,
            len(borrowed_connections),
        )
        for connection in borrowed_connections:
            try:
                await connection.interrupt()
            except (aiosqlite.Error, RuntimeError, ValueError) as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to interrupt borrowed SQLite read connection.",
                    operation=OPERATION_INTERRUPT_CONNECTION,
                    level="debug",
                )

    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        async with self._state_lock:
            self._shutdown = True
            if not self._borrowed_connections:
                self._borrowed_connections_drained.set()
        idle_connections: list[aiosqlite.Connection] = []
        while True:
            try:
                connection, _ = self._pool.get_nowait()
                idle_connections.append(connection)
            except asyncio.QueueEmpty:
                break
        for connection in idle_connections:
            await self._close_connection_safe(connection)
        if await self._wait_for_borrowed_drain(CONTROL_TIMEOUT_SEC):
            return
        await self._interrupt_borrowed_connections()
        if await self._wait_for_borrowed_drain(LOCAL_IO_TIMEOUT_SEC):
            return
        async with self._state_lock:
            borrowed_count = len(self._borrowed_connections)
        logger.critical(
            "FATAL: Read pool shutdown could not drain %d borrowed connection(s) after interrupt. Refusing to leak read connections past shutdown because that forks the WAL lineage.",
            borrowed_count,
        )
        raise DatabaseError(
            "Database read pool could not drain borrowed connections during shutdown.",
            operation=OPERATION_SHUTDOWN,
        )

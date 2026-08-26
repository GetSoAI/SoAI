"""SoAI - SQLite read connection pool and async read execution [backend/database/core/reader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Concatenate, NoReturn

import aiosqlite

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.sqlite.policy import build_sqlite_read_pragmas
from core.state.errors import DatabaseUnavailableError
from database.core.paths import DatabasePaths
from database.core.writer import DatabaseWriter
from database.io.read_pool import ReadConnectionPool

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = (
    "DatabaseReader",
    "DatabaseReaderDependencies",
)

LOGGER_NAME = "SoAI.database.core.reader"
OPERATION_DATABASE_CORE_EXECUTE_READ = "database_core.execute_read"
OPERATION_DATABASE_CORE_READER_SHUTDOWN = "database.core.reader.shutdown"


@dataclass(frozen=True, slots=True)
class DatabaseReaderDependencies:
    paths: DatabasePaths
    writer: DatabaseWriter
    connect_timeout: float
    max_pool_size: int
    read_mmap_size_mb: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DatabaseReaderDependencies",
            connect_timeout=self.connect_timeout,
            max_pool_size=self.max_pool_size,
            paths=self.paths,
            read_mmap_size_mb=self.read_mmap_size_mb,
            writer=self.writer,
        )


class DatabaseReader:
    def __init__(self, deps: DatabaseReaderDependencies) -> None:
        self._writer = deps.writer
        self._read_pool = ReadConnectionPool(
            deps.paths.db_path,
            is_shared_memory_mode=deps.paths.is_shared_memory_mode,
            pragmas=build_sqlite_read_pragmas(deps.read_mmap_size_mb),
            connect_timeout=deps.connect_timeout,
            max_pool_size=deps.max_pool_size,
            max_idle_time_sec=300.0,
        )

    def _handle_read_error(self, exception: BaseException) -> NoReturn:
        logger = get_logger(LOGGER_NAME)
        log_exception(
            logger,
            exception,
            message="Aiosqlite read operation failed",
            operation=OPERATION_DATABASE_CORE_EXECUTE_READ,
        )
        raise DatabaseUnavailableError(f"Read operation failed: {exception}") from exception

    async def execute_read[**P, T](
        self,
        func: Callable[Concatenate[aiosqlite.Connection, P], Awaitable[T]],
        *args: P.args,
        **named_args: P.kwargs,
    ) -> T:
        logger = get_logger(LOGGER_NAME)
        connection: aiosqlite.Connection | None = None
        if self._writer.is_faulted:
            raise DatabaseUnavailableError(
                "Database writer session is restarting. Read operations are not available.",
            )
        if not self._writer.init_complete_event.is_set():
            raise DatabaseUnavailableError(
                "Database is not yet initialized. Read operations are not available.",
            )
        try:
            connection = await self._read_pool.acquire()
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError) as exception:
            error_message = str(exception).lower()
            if "unable to open database file" in error_message or "readonly" in error_message:
                log_exception(
                    logger,
                    exception,
                    message="Database read-only connection failed",
                    operation=OPERATION_DATABASE_CORE_EXECUTE_READ,
                    details={"db_path": str(self._writer.db_path), "error": error_message},
                )
                raise DatabaseUnavailableError(
                    f"Database read access failed: {exception}. Verify database file exists and has proper read permissions.",
                ) from exception
            self._handle_read_error(exception)
        except aiosqlite.Error as exception:
            self._handle_read_error(exception)
        try:
            return await func(connection, *args, **named_args)
        except (aiosqlite.OperationalError, aiosqlite.DatabaseError) as exception:
            error_message = str(exception).lower()
            if "no such table" in error_message:
                log_exception(
                    logger,
                    exception,
                    message="Database schema incomplete - initialization may have failed",
                    operation=OPERATION_DATABASE_CORE_EXECUTE_READ,
                )
                raise DatabaseUnavailableError(
                    f"Database schema error: {exception}. Ensure database is fully initialized.",
                ) from exception
            self._handle_read_error(exception)
        except aiosqlite.Error as exception:
            self._handle_read_error(exception)
        finally:
            if connection is not None:
                await self._read_pool.release(connection)

    async def shutdown(self) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            await self._read_pool.shutdown()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to shutdown database read pool.",
                operation=OPERATION_DATABASE_CORE_READER_SHUTDOWN,
                level="critical",
            )
            raise
        logger.debug("Database read pool has been shut down.")

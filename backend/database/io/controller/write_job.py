"""SoAI - DB write job container for DatabaseIOController [backend/database/io/controller/write_job.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass

from core.database.write_storage import DatabaseWriteStorage
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.state.errors import DatabaseUnavailableError
from database.io.futures import (
    resolve_future_exception_threadsafe,
    resolve_future_result_threadsafe,
)
from database.io.internal_protocols import DatabaseCoreIOProtocol

__all__ = ("DatabaseWriteJob",)

LOGGER_NAME = "SoAI.database.io.write_job"


@dataclass(slots=True)
class DatabaseWriteJob[*Ts, T]:
    func: Callable[[sqlite3.Connection, *Ts], T]
    args: tuple[*Ts]
    future: asyncio.Future[T] | None
    cancelled: threading.Event | None
    operation_id: str
    operation_name: str
    storage: DatabaseWriteStorage | None = None

    def release_resources(self) -> None:
        if self.storage is not None:
            self.storage.completed.set()

    def is_cancelled(self) -> bool:
        cancelled = self.cancelled
        return bool(cancelled and cancelled.is_set())

    def resolve_unavailable(self) -> None:
        logger = get_logger(LOGGER_NAME)
        future = self.future
        if future is None:
            return
        resolve_future_exception_threadsafe(
            future,
            logger=logger,
            exception=DatabaseUnavailableError("Database is restarting."),
        )

    def resolve_exception(self, exception: BaseException) -> None:
        logger = get_logger(LOGGER_NAME)
        future = self.future
        if future is None:
            return
        resolve_future_exception_threadsafe(
            future,
            logger=logger,
            exception=exception,
        )

    def execute_once(self, conn: sqlite3.Connection, manager: DatabaseCoreIOProtocol) -> None:
        logger = get_logger(LOGGER_NAME)
        with ExitStack() as resources:
            if self.storage is not None:
                lease = resources.enter_context(
                    self.storage.provider.reserve_disk_space(
                        path=manager.db_path,
                        required_bytes=self.storage.required_bytes,
                        operation="database.write",
                        details={"operation_id": self.operation_id},
                    )
                )
                resources.enter_context(
                    claim_reserved_write(lease, size_bytes=self.storage.required_bytes)
                )
            result = manager.process_single_operation(
                conn,
                self.func,
                self.args,
                self.operation_id,
            )
        future = self.future
        if future is None:
            return
        if not self.is_cancelled():
            resolve_future_result_threadsafe(future, logger=logger, result=result)

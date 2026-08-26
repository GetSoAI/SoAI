"""SoAI - DB write job container for DatabaseIOController [backend/database/io/controller/write_job.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass

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

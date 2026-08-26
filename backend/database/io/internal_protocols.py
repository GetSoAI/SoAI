"""SoAI - Database I/O internal protocols and types [backend/database/io/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses
import sqlite3
import threading
from collections.abc import Callable
from enum import Enum
from types import TracebackType
from typing import TYPE_CHECKING, Protocol

import aiosqlite

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from core.database.protocols import DatabaseMetricsRecorderProtocol

__all__ = (
    "AsyncContextManagerProtocol",
    "DatabaseCoreIOProtocol",
    "DatabaseWriteJobProtocol",
    "DatabaseWriterSessionFault",
    "OperationCompletionRecord",
    "OperationStatus",
    "ShutdownSentinel",
)


@dataclasses.dataclass(frozen=True, slots=True)
class ShutdownSentinel: ...


class OperationStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMMITTED = "committed"
    FAILED = "failed"
    SKIPPED = "skipped"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclasses.dataclass(frozen=True, slots=True)
class OperationCompletionRecord:
    operation_id: str
    status: OperationStatus
    completed_at: float
    error_type: str | None = None


class DatabaseWriterSessionFault(StateError):
    __slots__ = ()


class AsyncContextManagerProtocol(Protocol):
    async def __aenter__(self) -> aiosqlite.Connection: ...

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> bool | None: ...


class DatabaseCoreIOProtocol(Protocol):
    db_path: str

    @property
    def is_shared_memory_mode(self) -> bool: ...

    @property
    def metrics_recorder(self) -> DatabaseMetricsRecorderProtocol | None: ...

    def process_single_operation[*Ts, T](
        self,
        conn: sqlite3.Connection,
        func: Callable[[sqlite3.Connection, *Ts], T],
        args: tuple[*Ts],
        operation_id: str,
    ) -> T: ...

    def get_operation_status(self, operation_id: str) -> str | None: ...


class DatabaseWriteJobProtocol(Protocol):
    operation_id: str
    operation_name: str
    cancelled: threading.Event | None

    def is_cancelled(self) -> bool: ...

    def resolve_unavailable(self) -> None: ...

    def resolve_exception(self, exception: BaseException) -> None: ...

    def execute_once(self, conn: sqlite3.Connection, manager: DatabaseCoreIOProtocol) -> None: ...

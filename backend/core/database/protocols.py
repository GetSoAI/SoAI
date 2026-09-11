"""SoAI - Core database Protocol interfaces [backend/core/database/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Concatenate, Protocol

if TYPE_CHECKING:
    import aiosqlite

    from core.database.operation_status import DatabaseOperationStatus
    from core.database.vacuum_result import DatabaseVacuumResult, DatabaseVacuumStartupResult
    from core.types.json import JSONValue

__all__ = (
    "DatabaseCoreProtocol",
    "DatabaseFeatureGateProtocol",
    "DatabaseMetricsRecorderProtocol",
    "DatabaseOperationStatusProtocol",
    "DatabaseReaderProtocol",
    "DatabaseVacuumProtocol",
    "DatabaseWriterProtocol",
)


class DatabaseOperationStatusProtocol(Protocol):
    async def resolve(
        self,
        operation_id: str,
        *,
        now_ms: int | None = None,
    ) -> DatabaseOperationStatus: ...


class DatabaseMetricsRecorderProtocol(Protocol):
    def set_gauge(self, *keys: str, value: float) -> None: ...

    def record_timing(self, *keys: str, duration_ms: float) -> None: ...


class DatabaseFeatureGateProtocol(Protocol):
    def is_enabled(self, feature: str) -> bool: ...
    def ensure_feature_enabled(self, feature: str) -> None: ...


class DatabaseReaderProtocol(Protocol):
    async def execute_read[**P, TCo_co](
        self,
        func: Callable[Concatenate[aiosqlite.Connection, P], Awaitable[TCo_co]],
        *args: P.args,
        **named_args: P.kwargs,
    ) -> TCo_co: ...

    async def shutdown(self) -> None: ...


class DatabaseWriterProtocol(Protocol):
    db_path: str

    @property
    def is_initialized(self) -> bool: ...

    @property
    def is_faulted(self) -> bool: ...

    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def set_metrics_recorder(self, recorder: DatabaseMetricsRecorderProtocol | None) -> None: ...
    def bind_lineage_escalation(self, escalation: Callable[[str], None]) -> None: ...
    def get_operation_status(self, operation_id: str) -> str | None: ...
    def has_pending_write_operations(self) -> bool: ...

    async def queue_write_operation[*Ts, TCo_co](
        self,
        func: Callable[[sqlite3.Connection, *Ts], TCo_co],
        *args: *Ts,
        enqueue_timeout: float | None = None,
        operation_timeout: float | None = None,
        **named_args: JSONValue,
    ) -> TCo_co: ...


class DatabaseVacuumProtocol(Protocol):
    @property
    def startup_result(self) -> DatabaseVacuumStartupResult: ...

    async def run_startup_maintenance(self) -> DatabaseVacuumStartupResult: ...
    async def vacuum_database(
        self, *, require_reclaimable_space: bool = False
    ) -> DatabaseVacuumResult: ...
    async def shutdown(self) -> None: ...


class DatabaseCoreProtocol(Protocol):
    @property
    def reader(self) -> DatabaseReaderProtocol: ...

    @property
    def writer(self) -> DatabaseWriterProtocol: ...

    @property
    def vacuum(self) -> DatabaseVacuumProtocol: ...

    @property
    def features(self) -> DatabaseFeatureGateProtocol: ...

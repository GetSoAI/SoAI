"""SoAI - Database internal protocols [backend/database/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = (
    "DatabaseVacuumCoreProtocol",
    "ProcessHandleProtocol",
    "ProcessIOCountersProtocol",
)


class DatabaseVacuumCoreProtocol(Protocol):
    db_path: str

    @property
    def is_shared_memory_mode(self) -> bool: ...

    @property
    def last_vacuum_timestamp(self) -> float | None: ...

    def set_last_vacuum_timestamp(self, timestamp: float | None) -> None: ...

    async def vacuum_database(self) -> dict[str, int | float]: ...


class ProcessIOCountersProtocol(Protocol):
    @property
    def read_bytes(self) -> int: ...

    @property
    def write_bytes(self) -> int: ...


class ProcessHandleProtocol(Protocol):
    def io_counters(self) -> ProcessIOCountersProtocol: ...

"""SoAI - Database internal protocols [backend/database/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = (
    "ProcessHandleProtocol",
    "ProcessIOCountersProtocol",
)


class ProcessIOCountersProtocol(Protocol):
    @property
    def read_bytes(self) -> int: ...

    @property
    def write_bytes(self) -> int: ...


class ProcessHandleProtocol(Protocol):
    def io_counters(self) -> ProcessIOCountersProtocol: ...

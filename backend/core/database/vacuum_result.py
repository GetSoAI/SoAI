"""SoAI - Database vacuum result contracts [backend/core/database/vacuum_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

__all__ = ("DatabaseVacuumResult", "DatabaseVacuumStatusValue", "DatabaseVacuumStartupResult")


class DatabaseVacuumStatusValue(StrEnum):
    COMPLETED = "completed"
    INSUFFICIENT_RECLAIMABLE_SPACE = "insufficient_reclaimable_space"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    BUSY = "busy"
    DISK_FULL = "disk_full"


@dataclass(frozen=True, slots=True)
class DatabaseVacuumResult:
    status: DatabaseVacuumStatusValue
    size_before_bytes: int
    size_after_bytes: int
    reclaimable_bytes: int
    reclaimed_bytes: int
    elapsed_sec: float
    timestamp_persisted: bool = False


@dataclass(frozen=True, slots=True)
class DatabaseVacuumStartupResult:
    status: Literal["not_run", "disabled", "not_due", "skipped", "completed", "degraded"]
    reason: str | None = None
    result: DatabaseVacuumResult | None = None

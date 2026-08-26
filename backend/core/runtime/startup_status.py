"""SoAI - Startup phase status contracts [backend/core/runtime/startup_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = (
    "StartupPhaseResult",
    "StartupPhaseStatus",
)


class StartupPhaseStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED_BY_SHUTDOWN = "cancelled_by_shutdown"


@dataclass(frozen=True, slots=True)
class StartupPhaseResult:
    status: StartupPhaseStatus
    message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is StartupPhaseStatus.SUCCESS

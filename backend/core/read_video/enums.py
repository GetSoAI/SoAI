"""SoAI - Core read_video job and artifact status enums [backend/core/read_video/enums.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

__all__ = (
    "ReadVideoArtifactStatus",
    "ReadVideoJobStatus",
    "ReadVideoLeaseResult",
)


class ReadVideoJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        return self in (
            ReadVideoJobStatus.COMPLETED,
            ReadVideoJobStatus.CANCELLED,
            ReadVideoJobStatus.FAILED,
            ReadVideoJobStatus.INTERRUPTED,
        )


class ReadVideoArtifactStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ReadVideoLeaseResult(str, Enum):
    ACQUIRED = "acquired"
    BUSY = "busy"
    COMPLETED = "completed"
    NOT_FOUND = "not_found"

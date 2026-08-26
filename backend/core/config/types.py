"""SoAI - Core configuration state dataclasses [backend/core/config/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "KnownFileState",
    "ScanReadFailure",
)


@dataclass(frozen=True, slots=True)
class KnownFileState:
    mtime: float
    size: int
    content_hash: str | None


@dataclass(frozen=True, slots=True)
class ScanReadFailure:
    next_retry_at: float
    delay_seconds: float
    error_signature: str

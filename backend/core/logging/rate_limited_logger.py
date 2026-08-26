"""SoAI - Rate-limited logger utility [backend/core/logging/rate_limited_logger.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass

__all__ = ("RateLimitedLogger",)


@dataclass(slots=True)
class RateLimitedLogger:
    interval_seconds: float
    _last_warning_monotonic: float = 0.0
    _suppressed_count: int = 0

    def should_emit(self, *, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        if self.interval_seconds <= 0:
            suppressed = self._suppressed_count
            self._suppressed_count = 0
            return True, suppressed
        if current - self._last_warning_monotonic >= self.interval_seconds:
            suppressed = self._suppressed_count
            self._last_warning_monotonic = current
            self._suppressed_count = 0
            return True, suppressed
        self._suppressed_count += 1
        return False, 0

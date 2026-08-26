"""SoAI - Core progress speed calculation utility [backend/core/progress/speed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass, field

__all__ = ("SpeedCalculator",)


@dataclass(slots=True)
class SpeedCalculator:
    _last_time: float = field(default=0.0, repr=False)
    _last_bytes: int = field(default=0, repr=False)
    speed: float = field(default=0.0, repr=False)
    _ema_alpha: float = field(default=0.3, repr=False)

    def update(self, downloaded_bytes: int, *, force_sample: bool = False) -> float:
        current_time = time.monotonic()
        normalized_bytes = max(0, int(downloaded_bytes))
        if self._last_time <= 0:
            self._last_time = current_time
            self._last_bytes = normalized_bytes
            return self.speed
        if normalized_bytes <= self._last_bytes:
            return self.speed
        elapsed = current_time - self._last_time
        if elapsed <= 0:
            return self.speed
        if elapsed < 0.01 and not force_sample:
            return self.speed
        bytes_delta = normalized_bytes - self._last_bytes
        instant_speed = bytes_delta / elapsed
        if self.speed > 0:
            self.speed = self._ema_alpha * instant_speed + (1 - self._ema_alpha) * self.speed
        else:
            self.speed = instant_speed
        self._last_time = current_time
        self._last_bytes = normalized_bytes
        return self.speed

    def reset(self) -> None:
        self._last_time = 0.0
        self._last_bytes = 0
        self.speed = 0.0

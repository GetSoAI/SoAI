"""SoAI - Monotonic clock helpers in milliseconds [backend/core/timing/monotonic.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

__all__ = ("monotonic_ms",)


def monotonic_ms() -> int:
    return time.monotonic_ns() // 1_000_000

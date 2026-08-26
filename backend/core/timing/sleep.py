"""SoAI - Sync sleep helper for deterministic waits [backend/core/timing/sleep.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading

__all__ = ("sleep_seconds",)


def sleep_seconds(seconds: float) -> None:
    threading.Event().wait(seconds)

"""SoAI - Enqueue warning tracker for queue overflow [backend/features/api/runtime/container/enqueue_warning_tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
import time

from core.logging.protocols import TraceLogger

__all__ = ("EnqueueWarningTracker",)


class EnqueueWarningTracker:
    __slots__ = ("_throttle_seconds", "_warn_counts", "_warn_last_log", "_warn_lock")

    def __init__(self, *, throttle_seconds: float = 10.0) -> None:
        self._warn_counts: dict[str, int] = {}
        self._warn_last_log: dict[str, float] = {}
        self._warn_lock = threading.Lock()
        self._throttle_seconds = float(throttle_seconds)

    def record_queue_full(self, context_label: str, *, logger: TraceLogger) -> None:
        now = time.monotonic()
        with self._warn_lock:
            self._warn_counts[context_label] = self._warn_counts.get(context_label, 0) + 1
            last_log = self._warn_last_log.get(context_label, 0.0)
            if now - last_log < self._throttle_seconds:
                return
            dropped_count = self._warn_counts[context_label]
            logger.warning(
                "Failed to enqueue event for %s: queue full (%d dropped in last %.0fs)",
                context_label,
                dropped_count,
                self._throttle_seconds,
            )
            self._warn_counts[context_label] = 0
            self._warn_last_log[context_label] = now

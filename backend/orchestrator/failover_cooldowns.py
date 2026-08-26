"""SoAI - Orchestrator transient failover cooldown tracking [backend/orchestrator/failover_cooldowns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = ("TransientFailureCooldowns",)


class TransientFailureCooldowns:
    def __init__(self, cooldown_seconds: float) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._failures: dict[str, float] = {}

    def update_cooldown(self, cooldown_seconds: float) -> None:
        self._cooldown_seconds = cooldown_seconds

    def record(self, universal_id: str) -> None:
        if not universal_id:
            return
        self._failures[universal_id] = time.monotonic()

    def clear(self, universal_id: str) -> None:
        if not universal_id:
            return
        self._failures.pop(universal_id, None)

    def is_on_cooldown(self, universal_id: str) -> bool:
        if not universal_id:
            return False
        failure_time = self._failures.get(universal_id)
        cooldown_seconds = self._cooldown_seconds
        if failure_time is None:
            return False
        return time.monotonic() - failure_time < cooldown_seconds

    def cleanup(self, logger: TraceLogger) -> int:
        now = time.monotonic()
        cooldown_seconds = self._cooldown_seconds
        keys_to_delete = [
            universal_id
            for universal_id, fail_time in self._failures.items()
            if now - fail_time >= cooldown_seconds
        ]
        for universal_id in keys_to_delete:
            self._failures.pop(universal_id, None)
        if keys_to_delete:
            logger.trace("Cleaned up %s expired transient failures.", len(keys_to_delete))
        return len(keys_to_delete)

    def count(self) -> int:
        return len(self._failures)

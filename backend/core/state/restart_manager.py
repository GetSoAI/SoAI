"""SoAI - Restart requirement tracking [backend/core/state/restart_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.logging.protocols import LoggerProtocol
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC
from core.timing.epoch import epoch_seconds_float

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "RestartStateManager",
    "RestartStateManagerDependencies",
)


@dataclass(frozen=True, slots=True)
class RestartStateManagerDependencies:
    restart_pending_event: asyncio.Event
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="RestartStateManagerDependencies",
            logger=self.logger,
            restart_pending_event=self.restart_pending_event,
        )


class RestartStateManager:
    _MAX_NOTIFICATIONS = 25

    def __init__(self, deps: RestartStateManagerDependencies) -> None:
        self._restart_pending = deps.restart_pending_event
        self._logger = deps.logger
        self._restart_pid: int | None = None
        self._restart_timestamp_unix: float | None = None
        self._restart_timestamp_monotonic: float | None = None
        self._last_reminder_monotonic: float | None = None
        self._reasons: list[str] = []
        self._notifications: list[JSONDict] = []
        self._lock = asyncio.Lock()

    async def require_restart(self, reason: str, source: str = "unknown") -> None:
        async with self._lock:
            if not self._restart_pending.is_set():
                self._restart_pid = os.getpid()
                self._restart_timestamp_unix = epoch_seconds_float()
                self._restart_timestamp_monotonic = time.monotonic()
                self._logger.warning(
                    "Restart required: %s (source: %s, PID: %s)",
                    reason,
                    source,
                    self._restart_pid,
                )
                self._restart_pending.set()
                self._last_reminder_monotonic = self._restart_timestamp_monotonic
            self._register_notification(
                reason=reason,
                changed_path=source,
                timestamp=epoch_seconds_float(),
            )

    def _clear_restart_state_internal(self, reason: str) -> None:
        if self._restart_pending.is_set():
            self._logger.debug("Clearing restart requirement: %s", reason)
            self._restart_pending.clear()
            self._restart_pid = None
            self._restart_timestamp_unix = None
            self._restart_timestamp_monotonic = None
            self._reasons.clear()
        self._notifications.clear()

    async def clear_restart_requirement(self, reason: str = "restart_completed") -> None:
        async with self._lock:
            self._clear_restart_state_internal(reason)

    def _register_notification(self, *, reason: str, changed_path: str, timestamp: float) -> None:
        normalized_reason = (reason or "").strip()
        normalized_path = (changed_path or "").strip()
        entry: JSONDict = {
            "reason": normalized_reason,
            "path": normalized_path or None,
            "timestamp": timestamp,
        }
        existing_index = None
        for index, current in enumerate(self._notifications):
            if current["reason"] == entry["reason"] and current.get("path") == entry.get("path"):
                existing_index = index
                break
        if existing_index is not None:
            self._notifications[existing_index] = entry
        else:
            self._notifications.append(entry)
            if len(self._notifications) > self._MAX_NOTIFICATIONS:
                self._notifications = self._notifications[-self._MAX_NOTIFICATIONS :]
        if normalized_reason and normalized_reason not in self._reasons:
            self._reasons.append(normalized_reason)

    async def check_and_clear_stale_state(self) -> bool:
        async with self._lock:
            if not self._restart_pending.is_set():
                return False
            current_pid = os.getpid()
            if self._restart_pid is not None and self._restart_pid != current_pid:
                self._logger.warning(
                    "STALE RESTART STATE DETECTED: restart_pending was set by PID %s, but current PID is %s. Backend has restarted. Clearing stale state.",
                    self._restart_pid,
                    current_pid,
                )
                self._clear_restart_state_internal("stale_state_detected_pid_mismatch")
                return True
            return False

    def _try_log_reminder_unlocked(self) -> None:
        if not self._restart_pending.is_set():
            return
        if self._restart_timestamp_monotonic is None:
            return
        now = time.monotonic()
        last = self._last_reminder_monotonic or self._restart_timestamp_monotonic
        if now - last < LONG_IDLE_TIMEOUT_SEC:
            return
        reasons = ", ".join(self._reasons) if self._reasons else "unspecified"
        self._logger.debug(
            "Restart still required: pending since %s (PID: %s, reasons: %s)",
            self._restart_timestamp_unix,
            self._restart_pid,
            reasons,
        )
        self._last_reminder_monotonic = now

    def get_restart_info(self) -> JSONDict:
        required = self._restart_pending.is_set()
        if required:
            self._try_log_reminder_unlocked()
        timestamp = self._restart_timestamp_unix
        pid = self._restart_pid
        reasons = list(self._reasons)
        notifications = [entry.copy() for entry in self._notifications]
        return {
            "required": required,
            "timestamp": timestamp,
            "pid": pid,
            "reasons": reasons,
            "notifications": notifications,
        }

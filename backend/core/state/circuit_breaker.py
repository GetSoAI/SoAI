"""SoAI - Circuit breaker implementation used by core state management [backend/core/state/circuit_breaker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms

__all__ = (
    "CircuitBreaker",
    "CircuitBreakerState",
)

LOGGER_NAME = "SoAI.core.state.circuit_breaker"


def _new_failure_history() -> deque[tuple[float, int]]:
    return deque()


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


@dataclass(slots=True)
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout_sec: float = 300.0
    failure_window_sec: float = 300.0
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_at: float = 0.0
    last_failure_epoch_ms: int = 0
    _failure_history: deque[tuple[float, int]] = field(
        default_factory=_new_failure_history,
        init=False,
        repr=False,
        compare=False,
    )
    _half_open_probe_consumed: bool = field(default=False, init=False, repr=False, compare=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.failure_count > 0 and self.last_failure_at > 0.0:
            self._failure_history.append((self.last_failure_at, self.failure_count))

    def _replace_failure_history(self, failures: Iterable[tuple[float, int]]) -> None:
        self._failure_history.clear()
        self._failure_history.extend(failures)
        self.failure_count = sum(count for _, count in self._failure_history)

    def _prune_failure_window(self, now_monotonic: float) -> None:
        cutoff_monotonic = now_monotonic - self.failure_window_sec
        while self._failure_history and self._failure_history[0][0] < cutoff_monotonic:
            self._failure_history.popleft()
        self.failure_count = sum(count for _, count in self._failure_history)

    def _transition_open_to_half_open_if_due(self, now_monotonic: float) -> bool:
        if (
            self.state == CircuitBreakerState.OPEN
            and now_monotonic - self.last_failure_at > self.recovery_timeout_sec
        ):
            self.state = CircuitBreakerState.HALF_OPEN
            self._replace_failure_history(())
            self._half_open_probe_consumed = False
            get_logger(LOGGER_NAME).info(
                "Circuit breaker is now HALF-OPEN. Will allow one test request.",
            )
            return True
        return False

    def check_and_attempt_recovery(self) -> tuple[bool, bool]:
        with self._lock:
            did_transition = self._transition_open_to_half_open_if_due(time.monotonic())
            return (self.state == CircuitBreakerState.OPEN, did_transition)

    def is_open(self) -> bool:
        with self._lock:
            return self.state == CircuitBreakerState.OPEN

    def allow_request(self) -> bool:
        with self._lock:
            self._transition_open_to_half_open_if_due(time.monotonic())
            if self.state == CircuitBreakerState.OPEN:
                return False
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_probe_consumed:
                    return False
                self._half_open_probe_consumed = True
                return True
            return True

    def release_half_open_probe(self) -> None:
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self._half_open_probe_consumed = False

    def record_failure(self) -> None:
        with self._lock:
            now_monotonic = time.monotonic()
            now_epoch_ms = epoch_ms()
            if self.state == CircuitBreakerState.HALF_OPEN:
                self._replace_failure_history(((now_monotonic, 1),))
                self.last_failure_at = now_monotonic
                self.last_failure_epoch_ms = now_epoch_ms
                self.state = CircuitBreakerState.OPEN
                self._half_open_probe_consumed = False
                get_logger(LOGGER_NAME).warning(
                    "Circuit breaker has OPENED. Half-open probe failed. Cooldown: %.3fs",
                    self.recovery_timeout_sec,
                )
                return
            self._prune_failure_window(now_monotonic)
            self._failure_history.append((now_monotonic, 1))
            self.failure_count += 1
            self.last_failure_at = now_monotonic
            self.last_failure_epoch_ms = now_epoch_ms
            if (
                self.state == CircuitBreakerState.OPEN
                or self.failure_count >= self.failure_threshold
            ):
                if self.state != CircuitBreakerState.OPEN:
                    get_logger(LOGGER_NAME).warning(
                        "Circuit breaker has OPENED. Failure threshold (%s) reached. Cooldown: %.3fs",
                        self.failure_threshold,
                        self.recovery_timeout_sec,
                    )
                self.state = CircuitBreakerState.OPEN
                self._half_open_probe_consumed = False

    def record_success(self) -> None:
        with self._lock:
            if self.state != CircuitBreakerState.CLOSED:
                get_logger(LOGGER_NAME).info("Circuit breaker is now CLOSED.")
            self.state = CircuitBreakerState.CLOSED
            self._replace_failure_history(())
            self.last_failure_at = 0.0
            self.last_failure_epoch_ms = 0
            self._half_open_probe_consumed = False

    def force_open(self) -> None:
        with self._lock:
            if self.state != CircuitBreakerState.OPEN:
                get_logger(LOGGER_NAME).warning(
                    "Circuit breaker has OPENED. Forced open by lifecycle control.",
                )
            self.state = CircuitBreakerState.OPEN
            now_monotonic = time.monotonic()
            forced_failure_count = max(self.failure_count + 1, self.failure_threshold)
            self._replace_failure_history(((now_monotonic, forced_failure_count),))
            self.last_failure_at = now_monotonic
            self.last_failure_epoch_ms = epoch_ms()
            self._half_open_probe_consumed = False

    def update_config(
        self,
        *,
        failure_threshold: int,
        recovery_timeout_sec: float,
        failure_window_sec: float,
    ) -> bool:
        with self._lock:
            old_failure_count = self.failure_count
            old_last_failure_at = self.last_failure_at
            old_last_failure_epoch_ms = self.last_failure_epoch_ms
            self.failure_threshold = failure_threshold
            self.recovery_timeout_sec = recovery_timeout_sec
            self.failure_window_sec = failure_window_sec
            if self.state == CircuitBreakerState.CLOSED:
                self._prune_failure_window(time.monotonic())
                if self.failure_count == 0:
                    self.last_failure_at = 0.0
                    self.last_failure_epoch_ms = 0
            return (
                self.failure_count != old_failure_count
                or self.last_failure_at != old_last_failure_at
                or self.last_failure_epoch_ms != old_last_failure_epoch_ms
            )

"""SoAI - Monotonic deadline arithmetic helpers [backend/core/concurrency/deadlines.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

__all__ = (
    "MonotonicDeadline",
    "deadline_after",
    "deadline_remaining",
    "deadline_remaining_clamped",
    "is_deadline_expired",
    "wait_for_hard_deadline",
)


@dataclass(frozen=True, slots=True)
class MonotonicDeadline:
    deadline_monotonic: float

    def remaining_seconds(self) -> float:
        return deadline_remaining_clamped(self.deadline_monotonic)

    def expired(self) -> bool:
        return is_deadline_expired(self.deadline_monotonic)


def deadline_after(timeout_seconds: float) -> MonotonicDeadline:
    return MonotonicDeadline(time.monotonic() + max(0.0, float(timeout_seconds)))


def deadline_remaining(deadline_monotonic: float) -> float:
    return deadline_monotonic - time.monotonic()


def deadline_remaining_clamped(deadline_monotonic: float, *, minimum: float = 0.0) -> float:
    remaining = deadline_monotonic - time.monotonic()
    if remaining < minimum:
        return minimum
    return remaining


def is_deadline_expired(deadline_monotonic: float) -> bool:
    return time.monotonic() >= deadline_monotonic


async def wait_for_hard_deadline[Result](
    deadline_monotonic: float,
    wait_operation: Callable[[float], Awaitable[Result]],
) -> Result:
    remaining = deadline_remaining(deadline_monotonic)
    if remaining <= 0:
        raise TimeoutError("Deadline expired.")
    return await wait_operation(remaining)

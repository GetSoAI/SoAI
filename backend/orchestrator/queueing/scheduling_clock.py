"""SoAI - Restart-durable monotonic queue scheduling clock [backend/orchestrator/queueing/scheduling_clock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from core.validation.epoch import require_unix_epoch_ms

__all__ = (
    "QueueSchedulingClock",
    "QueueSchedulingClockDependencies",
)


@dataclass(frozen=True, slots=True)
class QueueSchedulingClockDependencies:
    database_tasks: DatabaseTasksProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="QueueSchedulingClockDependencies",
            database_tasks=self.database_tasks,
        )


class QueueSchedulingClock:
    def __init__(self, deps: QueueSchedulingClockDependencies) -> None:
        self._database_tasks = deps.database_tasks
        self._lock = asyncio.Lock()
        self._anchor_epoch_ms = int(epoch_ms())
        self._anchor_monotonic_ms = monotonic_ms()

    async def reserve_queued_at(self) -> float:
        async with self._lock:
            now_monotonic_ms = monotonic_ms()
            elapsed_ms = max(0, now_monotonic_ms - self._anchor_monotonic_ms)
            candidate_at_ms = max(
                self._anchor_epoch_ms + elapsed_ms,
                int(epoch_ms()),
            )
            require_unix_epoch_ms(
                candidate_at_ms,
                error_message="Queue scheduling clock produced an invalid epoch timestamp.",
            )
            reserved_at_ms = await self._database_tasks.reserve_orchestrator_queue_scheduling_time(
                candidate_at_ms,
            )
            require_unix_epoch_ms(
                reserved_at_ms,
                error_message="Queue scheduling clock repository returned an invalid timestamp.",
            )
            if reserved_at_ms < candidate_at_ms:
                raise StateError(
                    "Reserved queue scheduling timestamp preceded its candidate.",
                    details={
                        "candidate_at_ms": candidate_at_ms,
                        "reserved_at_ms": reserved_at_ms,
                    },
                )
            self._anchor_epoch_ms = reserved_at_ms
            self._anchor_monotonic_ms = now_monotonic_ms
            return reserved_at_ms / 1000.0

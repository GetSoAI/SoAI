"""SoAI - Durable mutation recovery quarantine health [backend/app/background/mutation_recovery_health.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryProtocol
from core.timing.epoch import epoch_ms

__all__ = (
    "MutationRecoveryHealthMonitor",
    "MutationRecoveryHealthMonitorDependencies",
    "MutationRecoveryHealthSnapshot",
)

LOGGER_NAME = "SoAI.app.background.mutation_recovery_health"


@dataclass(frozen=True, slots=True)
class MutationRecoveryHealthSnapshot:
    status: Literal["healthy", "degraded"]
    quarantined_conflict_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MutationRecoveryHealthMonitorDependencies:
    database_tasks: DatabaseTasksProtocol
    task_registry: TaskRegistryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MutationRecoveryHealthMonitorDependencies",
            database_tasks=self.database_tasks,
            task_registry=self.task_registry,
        )


class MutationRecoveryHealthMonitor:
    def __init__(self, deps: MutationRecoveryHealthMonitorDependencies) -> None:
        self._deps = deps
        self._snapshot = MutationRecoveryHealthSnapshot(
            status="healthy",
            quarantined_conflict_keys=(),
        )
        self._pending_terminal_task_ids: set[str] = set()

    @property
    def snapshot(self) -> MutationRecoveryHealthSnapshot:
        return self._snapshot

    async def refresh(self) -> MutationRecoveryHealthSnapshot:
        quarantined_task_ids = await self._deps.database_tasks.quarantine_exhausted_mutations(
            now_ms=epoch_ms(),
        )
        self._pending_terminal_task_ids.update(quarantined_task_ids)
        for task_id in tuple(sorted(self._pending_terminal_task_ids)):
            await self._deps.task_registry.get(task_id, force_refresh=True)
            self._pending_terminal_task_ids.remove(task_id)
        recoveries = await self._deps.database_tasks.query_recovery_required_admissions()
        conflict_keys = tuple(
            sorted(
                {conflict_key for recovery in recoveries for conflict_key in recovery.conflict_keys}
            )
        )
        if conflict_keys == self._snapshot.quarantined_conflict_keys:
            return self._snapshot
        self._snapshot = MutationRecoveryHealthSnapshot(
            status="degraded" if conflict_keys else "healthy",
            quarantined_conflict_keys=conflict_keys,
        )
        logger = get_logger(LOGGER_NAME)
        if conflict_keys:
            logger.warning(
                "Durable mutations require recovery; conflict keys are quarantined (exhausted_now=%s, conflict_keys=%s).",
                len(quarantined_task_ids),
                conflict_keys,
            )
        else:
            logger.info("Durable mutation recovery quarantine cleared.")
        return self._snapshot

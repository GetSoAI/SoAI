"""SoAI - Task registry dependency injection bundles [backend/tasks/registry/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.database.protocols_tasks import DatabaseTasksProtocol
    from core.events.protocols import EventBusProtocol
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.tasks.type_catalog import TaskTypeCatalog

__all__ = (
    "TaskRegistryConfig",
    "TaskRegistryDependencies",
)


@dataclass(frozen=True, slots=True)
class TaskRegistryConfig:
    max_concurrent_per_owner: int = 100
    max_concurrent_by_owner_type: dict[str, int] = field(default_factory=dict[str, int])
    default_ttl_ms: int = 3_600_000
    cleanup_interval_ms: int = 300_000
    memory_cache_max_size: int = 10000
    terminal_grace_ms: int = 60_000
    stuck_task_timeout_ms: int = 3_600_000


@dataclass(frozen=True, slots=True)
class TaskRegistryDependencies:
    database_tasks: DatabaseTasksProtocol
    event_bus: EventBusProtocol
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    task_catalog: TaskTypeCatalog
    config: TaskRegistryConfig

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TaskRegistryDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_coordinator=self.cancellation_coordinator,
            cancellation_history=self.cancellation_history,
            config=self.config,
            database_tasks=self.database_tasks,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            task_catalog=self.task_catalog,
        )

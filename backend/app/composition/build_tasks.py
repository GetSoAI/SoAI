"""SoAI - Task registry component assembly [backend/app/composition/build_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.database.protocols_tasks import DatabaseTasksProtocol
from core.events.protocols import EventBusProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.protocols_query import DatabaseTaskQueriesProtocol
from core.tasks.type_catalog import TaskTypeCatalog
from tasks.registry.config_resolution import (
    TaskRegistryInitValues,
    resolve_task_registry_init_values,
)
from tasks.registry.dependencies import TaskRegistryConfig, TaskRegistryDependencies
from tasks.registry.queries import TaskRegistryQueries
from tasks.registry.query_dependencies import TaskRegistryQueriesDependencies
from tasks.registry.registry import TaskRegistry
from tasks.registry.storage import validate_task_registry_dependencies

__all__ = (
    "TaskRegistryFactoryResult",
    "TaskRegistryInitValues",
    "create_task_registry",
    "resolve_task_registry_init_values",
)


@dataclass(frozen=True, slots=True)
class TaskRegistryFactoryResult:
    registry: TaskRegistry
    queries: TaskRegistryQueries


def create_task_registry(
    database_tasks: DatabaseTasksProtocol,
    database_task_queries: DatabaseTaskQueriesProtocol,
    event_bus: EventBusProtocol,
    cancellation_coordinator: CancellationCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    task_catalog: TaskTypeCatalog,
    *,
    max_concurrent_per_owner: int | None = None,
    max_concurrent_by_owner_type: dict[str, int] | None = None,
    default_ttl_ms: int | None = None,
    cleanup_interval_ms: int | None = None,
    memory_cache_max_size: int | None = None,
    terminal_grace_ms: int | None = None,
    stuck_task_timeout_ms: int | None = None,
) -> TaskRegistryFactoryResult:
    validate_task_registry_dependencies(database_tasks, event_bus)
    config = TaskRegistryConfig(
        max_concurrent_per_owner=(
            int(max_concurrent_per_owner) if max_concurrent_per_owner is not None else 100
        ),
        max_concurrent_by_owner_type=(
            dict(max_concurrent_by_owner_type) if max_concurrent_by_owner_type is not None else {}
        ),
        default_ttl_ms=(int(default_ttl_ms) if default_ttl_ms is not None else 3_600_000),
        cleanup_interval_ms=(
            int(cleanup_interval_ms) if cleanup_interval_ms is not None else 300_000
        ),
        memory_cache_max_size=(
            int(memory_cache_max_size) if memory_cache_max_size is not None else 10000
        ),
        terminal_grace_ms=(int(terminal_grace_ms) if terminal_grace_ms is not None else 60_000),
        stuck_task_timeout_ms=(
            int(stuck_task_timeout_ms) if stuck_task_timeout_ms is not None else 3_600_000
        ),
    )
    registry_deps = TaskRegistryDependencies(
        database_tasks=database_tasks,
        event_bus=event_bus,
        cancellation_coordinator=cancellation_coordinator,
        cancellation_history=cancellation_history,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        task_catalog=task_catalog,
        config=config,
    )
    registry = TaskRegistry(registry_deps)
    registry.initialize_subscriptions()
    registry.start_cleanup_loop()
    queries_deps = TaskRegistryQueriesDependencies(
        database_tasks=database_tasks,
        database_task_queries=database_task_queries,
        task_catalog=task_catalog,
    )
    queries = TaskRegistryQueries(queries_deps)
    return TaskRegistryFactoryResult(registry=registry, queries=queries)

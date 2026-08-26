"""SoAI - Plugin lifecycle dependency definitions [backend/plugins/lifecycle_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.protocols import CancellationTokenProtocol
from core.di.validation import require_dependencies
from core.plugins.protocols_lifecycle import PluginLifecycleLocksProtocol
from core.runtime.protocols import ServiceLifecycleProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    SpawnTrackedTaskCallable,
    TaskCancellationBinderProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.tasks.protocols_operations import (
    TaskRegistryCancelCallable,
    TaskRegistryCreateCallable,
    TaskRegistryFinalizeCallable,
    TaskRegistryUpdateStatusCallable,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ActiveCancellationRecord",
    "PluginLifecycleDependencies",
)


@dataclass(slots=True)
class ActiveCancellationRecord:
    task: asyncio.Task[None]
    token: CancellationTokenProtocol
    task_type: str
    plugin_name: str | None
    metadata: JSONDict


@dataclass(frozen=True, slots=True)
class PluginLifecycleDependencies:
    lifecycle: ServiceLifecycleProtocol
    locks: PluginLifecycleLocksProtocol
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    create_managed_task: SpawnTrackedTaskCallable
    task_create: TaskRegistryCreateCallable
    task_cancel: TaskRegistryCancelCallable
    task_finalize: TaskRegistryFinalizeCallable
    task_update_status: TaskRegistryUpdateStatusCallable
    plugin_task_ttl_ms: int
    plugin_task_type_map: dict[str, TaskTypeId]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginLifecycleDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_coordinator=self.cancellation_coordinator,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            create_managed_task=self.create_managed_task,
            lifecycle=self.lifecycle,
            locks=self.locks,
            plugin_task_ttl_ms=self.plugin_task_ttl_ms,
            plugin_task_type_map=self.plugin_task_type_map,
            task_cancel=self.task_cancel,
            task_create=self.task_create,
            task_finalize=self.task_finalize,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
            task_update_status=self.task_update_status,
            token_collection=self.token_collection,
        )

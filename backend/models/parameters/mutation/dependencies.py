"""SoAI - Parameter mutation service dependencies [backend/models/parameters/mutation/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.logging.protocols import LoggerProtocol
from core.tasks.protocols import (
    SpawnTrackedTaskCallable,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from models.parameters.mutation_ordering import MutationCallable

__all__ = ("ParameterMutationServiceDependencies",)


@dataclass(frozen=True, slots=True)
class ParameterMutationServiceDependencies:
    logger: LoggerProtocol
    shutdown_event: asyncio.Event
    spawn_tracked_task: SpawnTrackedTaskCallable
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    num_workers: int
    update_executor: Callable[[str, JSONDict, int | None], Awaitable[None]]
    delete_executor: Callable[[str, list[str], int | None], Awaitable[None]]
    mutation_executor: Callable[[str, str, int | None, MutationCallable], Awaitable[None]]
    task_registry: TaskRegistryProtocol
    update_queue_max_size: int = 20000
    mutation_idle_timeout: float = 30.0
    max_mutation_workers: int = 100

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ParameterMutationServiceDependencies",
            cancellation_binder=self.cancellation_binder,
            delete_executor=self.delete_executor,
            finalizer_tracker=self.finalizer_tracker,
            logger=self.logger,
            max_mutation_workers=self.max_mutation_workers,
            mutation_executor=self.mutation_executor,
            mutation_idle_timeout=self.mutation_idle_timeout,
            num_workers=self.num_workers,
            shutdown_event=self.shutdown_event,
            spawn_tracked_task=self.spawn_tracked_task,
            task_registry=self.task_registry,
            update_executor=self.update_executor,
            update_queue_max_size=self.update_queue_max_size,
        )

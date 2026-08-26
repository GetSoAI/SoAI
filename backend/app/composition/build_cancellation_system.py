"""SoAI - Cancellation system component assembly [backend/app/composition/build_cancellation_system.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.logging.protocols import LoggerProtocol
from core.tasks.cancellation_coordinator import (
    CancellationCoordinator,
    CancellationCoordinatorDependencies,
)
from core.tasks.cancellation_event_bus import (
    CancellationEventBus,
    CancellationEventBusDependencies,
)
from core.tasks.cancellation_history import (
    CancellationHistory,
    CancellationHistoryDependencies,
)
from core.tasks.task_cancellation_binder import (
    TaskCancellationBinder,
    TaskCancellationBinderDependencies,
)
from core.tasks.task_finalizer_tracker import (
    TaskFinalizerTracker,
    TaskFinalizerTrackerDependencies,
)
from core.tasks.token_collection import TokenCollection, TokenCollectionDependencies

__all__ = (
    "CancellationSystem",
    "build_cancellation_coordinator",
    "build_cancellation_event_bus",
    "build_cancellation_history",
    "build_cancellation_system",
    "build_task_cancellation_binder",
    "build_task_finalizer_tracker",
    "build_token_collection",
)


@dataclass(frozen=True, slots=True)
class CancellationSystem:
    token_collection: TokenCollection
    history: CancellationHistory
    event_bus: CancellationEventBus
    finalizer_tracker: TaskFinalizerTracker
    binder: TaskCancellationBinder
    coordinator: CancellationCoordinator


def build_token_collection() -> TokenCollection:
    return TokenCollection(TokenCollectionDependencies())


def build_cancellation_history(*, max_history: int) -> CancellationHistory:
    return CancellationHistory(CancellationHistoryDependencies(max_history=max_history))


def build_cancellation_event_bus(
    *,
    logger: LoggerProtocol,
    queue_size: int,
) -> CancellationEventBus:
    return CancellationEventBus(
        CancellationEventBusDependencies(logger=logger, queue_size=queue_size),
    )


def build_task_finalizer_tracker() -> TaskFinalizerTracker:
    return TaskFinalizerTracker(TaskFinalizerTrackerDependencies())


def build_task_cancellation_binder(
    *,
    token_collection: TokenCollection,
    history: CancellationHistory,
    event_bus: CancellationEventBus,
    finalizer_tracker: TaskFinalizerTracker,
) -> TaskCancellationBinder:
    return TaskCancellationBinder(
        TaskCancellationBinderDependencies(
            token_collection=token_collection,
            history=history,
            event_bus=event_bus,
            finalizer_tracker=finalizer_tracker,
        ),
    )


def build_cancellation_coordinator(
    *,
    token_collection: TokenCollection,
    history: CancellationHistory,
    event_bus: CancellationEventBus,
) -> CancellationCoordinator:
    return CancellationCoordinator(
        CancellationCoordinatorDependencies(
            token_collection=token_collection,
            history=history,
            event_bus=event_bus,
        ),
    )


def build_cancellation_system(
    *,
    logger: LoggerProtocol,
    max_history: int = 2048,
    listener_queue_size: int = 1,
) -> CancellationSystem:
    token_collection = build_token_collection()
    history = build_cancellation_history(max_history=max_history)
    event_bus = build_cancellation_event_bus(
        logger=logger,
        queue_size=listener_queue_size,
    )
    finalizer_tracker = build_task_finalizer_tracker()
    binder = build_task_cancellation_binder(
        token_collection=token_collection,
        history=history,
        event_bus=event_bus,
        finalizer_tracker=finalizer_tracker,
    )
    coordinator = build_cancellation_coordinator(
        token_collection=token_collection,
        history=history,
        event_bus=event_bus,
    )
    return CancellationSystem(
        token_collection=token_collection,
        history=history,
        event_bus=event_bus,
        finalizer_tracker=finalizer_tracker,
        binder=binder,
        coordinator=coordinator,
    )

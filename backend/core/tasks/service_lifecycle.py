"""SoAI - Service lifecycle primitives for background workers [backend/core/tasks/service_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.concurrency.task_groups import ManagedTaskGroup
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

__all__ = (
    "ServiceLifecycle",
    "ServiceLifecycleDependencies",
    "initialize_managed_task_group",
)


@dataclass(frozen=True, slots=True)
class ServiceLifecycleDependencies:
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    managed_task_group_label: str | None = None
    managed_task_group_logger: LoggerProtocol | None = None
    managed_task_group_operation_name: str | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ServiceLifecycleDependencies",
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
        )


class ServiceLifecycle:

    def __init__(self, deps: ServiceLifecycleDependencies) -> None:
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.cancellation_binder = deps.cancellation_binder
        self.finalizer_tracker = deps.finalizer_tracker
        self.managed_task_group = _create_managed_task_group(
            label=deps.managed_task_group_label,
            logger=deps.managed_task_group_logger,
            operation_name=deps.managed_task_group_operation_name,
        )
        self.disabled = False

    def enable(self) -> None:
        self.disabled = False

    def require_enabled(self, owner: str) -> None:
        if self.disabled:
            raise StateError(f"{owner} is disabled.")


def initialize_managed_task_group(
    label: str,
    *,
    logger: LoggerProtocol,
    error_message: str,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    operation_name: str | None = None,
) -> tuple[
    ServiceLifecycle,
    asyncio.Event,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    ManagedTaskGroup,
]:
    deps = ServiceLifecycleDependencies(
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        managed_task_group_label=label,
        managed_task_group_logger=logger,
        managed_task_group_operation_name=operation_name,
    )
    lifecycle = ServiceLifecycle(deps)
    managed_task_group = lifecycle.managed_task_group
    if managed_task_group is None:
        raise StateError(error_message)
    return (
        lifecycle,
        lifecycle.shutdown_event,
        lifecycle.cancellation_binder,
        lifecycle.finalizer_tracker,
        managed_task_group,
    )


def _create_managed_task_group(
    *,
    label: str | None,
    logger: LoggerProtocol | None,
    operation_name: str | None = None,
) -> ManagedTaskGroup | None:
    if not label:
        return None
    return ManagedTaskGroup(label=label, logger=logger, operation_name=operation_name)

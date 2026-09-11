"""SoAI - Core service lifecycle protocols [backend/core/lifecycle/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.concurrency.task_groups import ManagedTaskGroup
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("ServiceLifecycleProtocol", "Shutdownable")


class Shutdownable(Protocol):
    async def shutdown(self) -> None: ...


class ServiceLifecycleProtocol(Protocol):
    shutdown_event: asyncio.Event
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    managed_task_group: ManagedTaskGroup | None
    disabled: bool

    def enable(self) -> None: ...

    def require_enabled(self, owner: str) -> None: ...

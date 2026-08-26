"""SoAI - Main state override task ownership [backend/orchestrator/state/main_state_overrides.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.events.types_system import SoAIMainState, SystemMainStateOverrideEvent
from core.logging.protocols import TraceLogger
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

__all__ = ("MainStateOverrideCoordinator",)


class MainStateOverrideCoordinator:
    def __init__(
        self,
        *,
        cancellation_binder: TaskCancellationBinderProtocol,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        logger: TraceLogger,
    ) -> None:
        self._cancellation_binder = cancellation_binder
        self._finalizer_tracker = finalizer_tracker
        self._logger = logger
        self._override: SoAIMainState | None = None
        self._override_event_id: str | None = None
        self._override_task: asyncio.Task[None] | None = None

    def is_override_active_locked(self) -> bool:
        return (
            self._override is not None
            and self._override_task is not None
            and (not self._override_task.done())
        )

    def resolve_effective_state_locked(self, base_state: SoAIMainState) -> SoAIMainState:
        if self.is_override_active_locked():
            override_state = self._override
            if override_state is not None:
                return override_state
        return base_state

    def cancel_override_task_locked(self) -> None:
        task = self._override_task
        self._override_task = None
        if task is not None and (not task.done()):
            task.cancel()

    def set_override_locked(self, event: SystemMainStateOverrideEvent) -> None:
        self._override = event.state
        self._override_event_id = event.event_id

    def clear_override_locked(self) -> None:
        self._override = None
        self._override_event_id = None
        self._override_task = None

    def matches_event_locked(self, event_id: str) -> bool:
        return self._override_event_id == event_id

    def start_override_expiry_task(
        self,
        *,
        event: SystemMainStateOverrideEvent,
        on_expiry: Callable[[SystemMainStateOverrideEvent], Awaitable[None]],
    ) -> None:
        async def _clear_override_task() -> None:
            await asyncio.sleep(event.duration_sec)
            await on_expiry(event)

        self._override_task = spawn_tracked_task(
            _clear_override_task(),
            name=f"state-override-clear-{event.event_id}",
            cancellation_binder=self._cancellation_binder,
            finalizer_tracker=self._finalizer_tracker,
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "state_aggregator",
                    "override",
                    safe_or_hashed_segment(str(event.event_id)),
                ),
            ),
            owner="state_override_revert",
            metadata={"reason": event.reason, "duration_sec": event.duration_sec},
        )

    async def shutdown(self) -> None:
        task = self._override_task
        self._override_task = None
        self._override = None
        self._override_event_id = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            self._logger.debug("Main state override expiry task cancelled during shutdown.")

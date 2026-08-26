"""SoAI - Main system state control with base state and overrides [backend/orchestrator/state/main_state_controller.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import (
    SoAIMainState,
    SoAIMainStateChangedEvent,
    SystemMainStateOverrideEvent,
)
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_LOADING,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_READY_PENDING_DISPATCH,
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_BACKEND_UPDATING,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_UPDATE_ERROR,
)
from orchestrator.state.dependencies import MainStateControllerDependencies
from orchestrator.state.main_state_overrides import MainStateOverrideCoordinator

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates

__all__ = ("MainStateController",)

LOGGER_NAME = "SoAI.orchestrator.state.main_state_controller"
OPERATION = "main_state_controller.publish_state_change"


ACTIVE_PLUGIN_STATES: frozenset[str] = frozenset(
    {
        ORCH_STATE_PROCESSING,
        PLUGIN_STATE_BACKEND_INSTALLING,
        PLUGIN_STATE_BACKEND_UPDATING,
        ORCH_STATE_LOADING,
        ORCH_STATE_READY_PENDING_DISPATCH,
    },
)
ERROR_PLUGIN_STATES: frozenset[str] = frozenset(
    {
        ORCH_STATE_ERROR,
        ORCH_STATE_QUARANTINED,
        PLUGIN_STATE_INSTALL_ERROR,
        PLUGIN_STATE_LOAD_ERROR,
        PLUGIN_STATE_UPDATE_ERROR,
        PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
        PLUGIN_STATE_DELETE_ERROR,
    },
)


class MainStateController:
    def __init__(self, deps: MainStateControllerDependencies) -> None:
        self._event_bus = deps.event_bus
        self._main_state_lock = asyncio.Lock()
        self._main_state_base = SoAIMainState.STARTING
        self._main_state = SoAIMainState.STARTING
        self._shutdown_requested = False
        self._logger: TraceLogger = get_logger(LOGGER_NAME)
        self._override_coordinator = MainStateOverrideCoordinator(
            cancellation_binder=deps.cancellation_binder,
            finalizer_tracker=deps.finalizer_tracker,
            logger=self._logger,
        )

    def _is_override_active_locked(self) -> bool:
        return self._override_coordinator.is_override_active_locked()

    def _resolve_effective_state_locked(self) -> SoAIMainState:
        return self._override_coordinator.resolve_effective_state_locked(self._main_state_base)

    async def _publish_state_change(
        self,
        previous_state: SoAIMainState,
        new_state: SoAIMainState,
        reason: str | None = None,
    ) -> None:
        event = SoAIMainStateChangedEvent(new_state=new_state, previous_state=previous_state)
        context = f" (reason: {reason})" if reason else ""
        try:
            await self._event_bus.publish(event)
        except RuntimeError as exception:
            log_exception(
                self._logger,
                exception,
                message=(
                    f"Main state change from {previous_state.value} to {new_state.value}"
                    f" was dropped because the EventBus is not running{context}."
                ),
                operation=OPERATION,
                level="critical",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message=(
                    f"Unexpected error while publishing main state change from {previous_state.value}"
                    f" to {new_state.value}{context}"
                ),
                operation=OPERATION,
            )

    async def set_state(self, new_state: SoAIMainState, reason: str) -> None:
        previous_effective: SoAIMainState | None = None
        new_effective: SoAIMainState | None = None
        override_active = False
        async with self._main_state_lock:
            if self._shutdown_requested:
                return
            if self._main_state_base == new_state:
                return
            previous_effective = self._main_state
            self._main_state_base = new_state
            override_active = self._is_override_active_locked()
            new_effective = self._resolve_effective_state_locked()
            if new_effective != previous_effective:
                self._main_state = new_effective
                self._logger.info(
                    "Main state explicitly set to %s. Reason: %s",
                    new_effective.value,
                    reason,
                )
            elif override_active:
                self._logger.debug(
                    "Main state base updated to %s while override is active. Reason: %s",
                    new_state.value,
                    reason,
                )
        if (
            previous_effective is not None
            and new_effective is not None
            and new_effective != previous_effective
        ):
            await self._publish_state_change(previous_effective, new_effective, reason=reason)

    async def recalculate_state(
        self,
        all_plugin_states: ImmutablePluginStates,
        reason: str,
    ) -> SoAIMainState | None:
        async with self._main_state_lock:
            if self._shutdown_requested:
                return None
            base_state = self._main_state_base
            if base_state in [SoAIMainState.STARTING, SoAIMainState.STOPPING] and (
                reason not in {"post_startup_transition", "override_expired"}
            ):
                self._logger.trace(
                    f"Skipping main state recalculation; in lifecycle state: {base_state.value}",
                )
                return None
        is_any_plugin_in_error = any(
            plugin_state.get("status") in ERROR_PLUGIN_STATES
            for plugin_state in all_plugin_states.values()
        )
        is_any_plugin_active = any(
            plugin_state.get("status") in ACTIVE_PLUGIN_STATES
            for plugin_state in all_plugin_states.values()
        )
        if is_any_plugin_in_error:
            new_base_state = SoAIMainState.ERROR
        elif is_any_plugin_active:
            new_base_state = SoAIMainState.ACTIVE
        else:
            new_base_state = SoAIMainState.READY
        previous_effective: SoAIMainState | None = None
        new_effective: SoAIMainState | None = None
        override_active = False
        async with self._main_state_lock:
            if self._shutdown_requested:
                return None
            base_state = self._main_state_base
            if base_state in [SoAIMainState.STARTING, SoAIMainState.STOPPING] and (
                reason not in {"post_startup_transition", "override_expired"}
            ):
                return None
            if base_state == new_base_state:
                return None
            previous_effective = self._main_state
            self._main_state_base = new_base_state
            override_active = self._is_override_active_locked()
            new_effective = self._resolve_effective_state_locked()
            if new_effective != previous_effective:
                self._main_state = new_effective
                self._logger.info(
                    "Main state updated to %s. Reason: %s",
                    new_effective.value,
                    reason,
                )
            elif override_active:
                self._logger.trace(
                    f"Main state base recalculated to {new_base_state.value} but override is active: {new_effective.value}",
                )
        if (
            previous_effective is not None
            and new_effective is not None
            and new_effective != previous_effective
        ):
            await self._publish_state_change(previous_effective, new_effective, reason=reason)
            return new_effective
        return None

    async def get_state(self) -> dict[str, str]:
        async with self._main_state_lock:
            return {"state": self._resolve_effective_state_locked().value}

    async def _expire_override(
        self,
        event: SystemMainStateOverrideEvent,
        on_expiry_recalculate: Callable[[], Awaitable[None]],
    ) -> None:
        previous_after_expiry: SoAIMainState | None = None
        new_after_expiry: SoAIMainState | None = None
        async with self._main_state_lock:
            if self._shutdown_requested:
                return
            if not self._override_coordinator.matches_event_locked(event.event_id):
                return
            previous_after_expiry = self._main_state
            self._override_coordinator.clear_override_locked()
            new_after_expiry = self._resolve_effective_state_locked()
            self._main_state = new_after_expiry
        if (
            previous_after_expiry is not None
            and new_after_expiry is not None
            and new_after_expiry != previous_after_expiry
        ):
            await self._publish_state_change(
                previous_after_expiry,
                new_after_expiry,
                reason="override_expired",
            )
        await on_expiry_recalculate()

    async def apply_override(
        self,
        event: SystemMainStateOverrideEvent,
        on_expiry_recalculate: Callable[[], Awaitable[None]],
    ) -> None:
        previous_effective: SoAIMainState | None = None
        new_effective: SoAIMainState | None = None
        async with self._main_state_lock:
            if self._shutdown_requested:
                return
            self._override_coordinator.cancel_override_task_locked()
            previous_effective = self._main_state
            self._override_coordinator.set_override_locked(event)
            self._main_state = event.state
            self._logger.warning(
                "Main state override: %s for %s seconds. Reason: %s",
                event.state.value,
                event.duration_sec,
                event.reason,
            )
            self._override_coordinator.start_override_expiry_task(
                event=event,
                on_expiry=lambda override_event: self._expire_override(
                    override_event,
                    on_expiry_recalculate,
                ),
            )
            new_effective = self._main_state
        if (
            previous_effective is not None
            and new_effective is not None
            and new_effective != previous_effective
        ):
            await self._publish_state_change(previous_effective, new_effective, reason=event.reason)

    async def shutdown(self) -> None:
        async with self._main_state_lock:
            self._shutdown_requested = True
            self._override_coordinator.cancel_override_task_locked()
        await self._override_coordinator.shutdown()

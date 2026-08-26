"""SoAI - Plugin and main state aggregation with event coordination [backend/orchestrator/state/aggregator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.events.protocols import EventBusProtocol
from core.events.recent_event_tracker import RecentEventTracker
from core.events.types_base import Event
from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginPurgedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.events.types_system import SoAIMainState, SystemMainStateOverrideEvent
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.plugins.name_validation import require_plugin_name
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.task_cancellation_ops import generate_system_cancellation_id
from orchestrator.state.dependencies import StateAggregatorDependencies
from orchestrator.state.search_data_store import SearchDataStore

if TYPE_CHECKING:
    from core.state.health_status import PluginHealthStatus
    from core.state.state_names import PluginRuntimeStateName

    type EventCallback = Callable[[Event], Awaitable[None]]

__all__ = ("StateAggregator",)

LOGGER_NAME = "SoAI.orchestrator.state.aggregator"


MAIN_STATE_RECALC_DEBOUNCE_SEC: float = 0.1
MAIN_STATE_RECALC_REASON_PREVIEW_LIMIT: int = 3


class StateAggregator:
    def __init__(self, deps: StateAggregatorDependencies) -> None:
        self.event_bus: EventBusProtocol = deps.event_bus
        self._cancellation_binder = deps.cancellation_binder
        self._finalizer_tracker = deps.finalizer_tracker
        self._plugin_store = deps.plugin_store
        self._main_state_controller = deps.main_state_controller
        self.search_store = SearchDataStore()
        self._started = False
        self._shutdown_requested = False
        self._start_lock = asyncio.Lock()
        self._recalculation_lock = asyncio.Lock()
        self._pending_recalculation_reasons: set[str] = set()
        self._recalculation_signal = asyncio.Event()
        self._debounced_recalculation_task: asyncio.Task[None] | None = None
        self._logger: TraceLogger = get_logger(LOGGER_NAME)
        self._processed_state_change_events = RecentEventTracker()
        self._subscriptions: tuple[tuple[type[Event], EventCallback], ...] = ()
        self.get_main_state = self._main_state_controller.get_state
        self.get_all_plugin_states = self._plugin_store.get_all_states
        self.get_all_plugin_states_with_version = self._plugin_store.get_all_states_with_version

    async def _trigger_main_state_recalculation(self, reason: str) -> SoAIMainState | None:
        all_plugin_states = await self._plugin_store.get_all_states()
        return await self._main_state_controller.recalculate_state(all_plugin_states, reason)

    def _compose_recalculation_reason(self, reasons: set[str]) -> str:
        ordered_reasons = sorted(
            reason for reason in (raw_reason.strip() for raw_reason in reasons) if reason
        )
        if not ordered_reasons:
            return "plugin_state_change"
        if len(ordered_reasons) == 1:
            return ordered_reasons[0]
        preview_reasons = ordered_reasons[:MAIN_STATE_RECALC_REASON_PREVIEW_LIMIT]
        preview = ",".join(preview_reasons)
        remaining_count = len(ordered_reasons) - len(preview_reasons)
        if remaining_count > 0:
            preview = f"{preview},+{remaining_count}"
        return f"coalesced:{len(ordered_reasons)}:{preview}"

    async def _run_debounced_recalculation(self) -> None:
        current_task = asyncio.current_task()
        try:
            while True:
                await self._recalculation_signal.wait()
                self._recalculation_signal.clear()
                while True:
                    try:
                        await asyncio.wait_for(
                            self._recalculation_signal.wait(),
                            timeout=MAIN_STATE_RECALC_DEBOUNCE_SEC,
                        )
                        self._recalculation_signal.clear()
                    except TimeoutError:
                        break
                async with self._recalculation_lock:
                    reasons = set(self._pending_recalculation_reasons)
                    self._pending_recalculation_reasons.clear()
                if reasons:
                    await self._trigger_main_state_recalculation(
                        self._compose_recalculation_reason(reasons),
                    )
                async with self._recalculation_lock:
                    if (
                        not self._pending_recalculation_reasons
                        and not self._recalculation_signal.is_set()
                    ):
                        self._debounced_recalculation_task = None
                        return
        finally:
            async with self._recalculation_lock:
                if self._debounced_recalculation_task is current_task:
                    self._debounced_recalculation_task = None

    async def _schedule_debounced_recalculation(self, reason: str) -> None:
        normalized_reason = str(reason).strip() or "plugin_state_change"
        async with self._recalculation_lock:
            if self._shutdown_requested or not self._started:
                return
            self._pending_recalculation_reasons.add(normalized_reason)
            self._recalculation_signal.set()
            if (
                self._debounced_recalculation_task is not None
                and not self._debounced_recalculation_task.done()
            ):
                return
            self._debounced_recalculation_task = spawn_tracked_task(
                self._run_debounced_recalculation(),
                name="state-aggregator-main-state-recalculation",
                logger=self._logger,
                cancellation_binder=self._cancellation_binder,
                cancellation_id=generate_system_cancellation_id(
                    "state-aggregator-main-state-recalculation",
                ),
                owner="state_aggregator_main_state_recalculation",
                finalizer_tracker=self._finalizer_tracker,
            )

    async def _handle_plugin_state_changed(self, event: Event) -> None:
        if self._shutdown_requested or not self._started:
            return
        if not isinstance(
            event,
            PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent,
        ):
            return
        if await self._processed_state_change_events.has_recent(event.event_id):
            return
        status_changed = await self._plugin_store.apply_state_change(event)
        await self._processed_state_change_events.mark_processed(event.event_id)
        if status_changed:
            await self._schedule_debounced_recalculation(f"plugin_state_change:{event.plugin_name}")

    async def apply_authoritative_plugin_state_change(
        self,
        event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent,
    ) -> None:
        await self._handle_plugin_state_changed(event)

    async def _handle_plugin_purged(self, event: Event) -> None:
        if self._shutdown_requested or not self._started:
            return
        if not isinstance(event, PluginPurgedEvent):
            return
        await self._plugin_store.apply_purge(event.plugin_name)
        await self._schedule_debounced_recalculation(f"plugin_purged:{event.plugin_name}")

    async def _handle_main_state_override(self, event: Event) -> None:
        if self._shutdown_requested or not self._started:
            return
        if not isinstance(event, SystemMainStateOverrideEvent):
            return

        async def recalculate_after_expiry() -> None:
            await self._trigger_main_state_recalculation("override_expired")

        await self._main_state_controller.apply_override(event, recalculate_after_expiry)

    async def start(self) -> None:
        async with self._start_lock:
            if self._started:
                self._logger.warning("StateAggregator start() called but already started.")
                return
            await self._plugin_store.bootstrap_from_database()
            self._subscriptions = (
                (PluginInstallationStateChangedEvent, self._handle_plugin_state_changed),
                (PluginRuntimeStateChangedEvent, self._handle_plugin_state_changed),
                (PluginPurgedEvent, self._handle_plugin_purged),
                (SystemMainStateOverrideEvent, self._handle_main_state_override),
            )
            self._shutdown_requested = False
            self._started = True
            for event_type, callback in self._subscriptions:
                self.event_bus.subscribe(event_type, callback)

    async def shutdown(self) -> None:
        async with self._start_lock:
            self._shutdown_requested = True
            if not self._started:
                await self._main_state_controller.shutdown()
                return
            subscriptions = self._subscriptions
            self._subscriptions = ()
            self._started = False
        for event_type, callback in subscriptions:
            self.event_bus.unsubscribe(event_type, callback)
        task = self._debounced_recalculation_task
        self._debounced_recalculation_task = None
        self._recalculation_signal.clear()
        async with self._recalculation_lock:
            self._pending_recalculation_reasons.clear()
        if task is not None and (not task.done()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                self._logger.debug(
                    "StateAggregator debounced recalculation task cancelled during shutdown.",
                )
        await self._main_state_controller.shutdown()

    async def set_main_state(self, new_state: SoAIMainState, reason: str) -> None:
        normalized_reason = str(reason).strip() or "state_change"
        await self._main_state_controller.set_state(new_state, normalized_reason)

    async def recalculate_and_set_main_state(self, reason: str) -> SoAIMainState | None:
        normalized_reason = str(reason).strip() or "state_change"
        return await self._trigger_main_state_recalculation(normalized_reason)

    async def get_plugin_status(self, plugin_name: str) -> PluginRuntimeStateName:
        normalized_plugin_name = require_plugin_name(plugin_name)
        return await self._plugin_store.get_status(normalized_plugin_name)

    async def update_plugin_health_status(
        self,
        plugin_name: str,
        health_status: PluginHealthStatus,
    ) -> None:
        normalized_plugin_name = require_plugin_name(plugin_name)
        await self._plugin_store.update_health_status(normalized_plugin_name, health_status)

    async def get_plugin_health_statuses(self) -> dict[str, PluginHealthStatus]:
        return await self._plugin_store.get_health_statuses()

    async def get_state_version(self) -> int:
        return await self._plugin_store.get_state_version()

    async def clear_purged_status(self, plugin_name: str) -> None:
        normalized_plugin_name = require_plugin_name(plugin_name)
        await self._plugin_store.clear_purged_status(normalized_plugin_name)

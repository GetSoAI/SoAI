"""SoAI - Runtime lifecycle state side effects and replay deduplication [backend/orchestrator/lifecycle/state_change_side_effects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import override

from core.di.validation import require_dependencies
from core.events.recent_event_tracker import RecentEventTracker
from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginRuntimeStateChangedEvent,
)
from core.logging.trace import get_logger
from core.state.protocols_publication import RuntimeStatePublicationSideEffectsProtocol
from core.state.state_names import ORCH_STATE_STOPPED, PLUGIN_STATE_STOPPED
from core.state.state_transition_sets import INTERRUPTIBLE_IDLE_STATES
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_bool_flag
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)
from orchestrator.plugin_state import PluginState
from orchestrator.types import OrchestratorDependencies

__all__ = (
    "RuntimeStateSideEffects",
    "RuntimeStateSideEffectsDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.state_change_side_effects"


@dataclass(frozen=True, slots=True)
class RuntimeStateSideEffectsDependencies:
    orchestrator: OrchestratorDependencies
    state: LifecycleStateAccessorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="RuntimeStateSideEffectsDependencies",
            orchestrator=self.orchestrator,
            state=self.state,
        )


class RuntimeStateSideEffects(RuntimeStatePublicationSideEffectsProtocol):
    def __init__(self, deps: RuntimeStateSideEffectsDependencies) -> None:
        self._deps = deps
        self._processed_state_change_events = RecentEventTracker()

    @override
    async def apply_local_publication(self, event: PluginRuntimeStateChangedEvent) -> None:
        await self._apply_state_change_side_effects(event, log_transition=False)
        await self._processed_state_change_events.mark_processed(event.event_id)

    @override
    async def apply_replayed_publication(
        self,
        event: PluginRuntimeStateChangedEvent | PluginInstallationStateChangedEvent,
    ) -> None:
        if await self._processed_state_change_events.has_recent(event.event_id):
            return
        await self._apply_state_change_side_effects(event, log_transition=True)
        await self._processed_state_change_events.mark_processed(event.event_id)

    async def _apply_state_change_side_effects(
        self,
        event: PluginRuntimeStateChangedEvent | PluginInstallationStateChangedEvent,
        *,
        log_transition: bool,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        details: JSONDict = {}
        if isinstance(event, PluginRuntimeStateChangedEvent):
            details = event.details
        plugin_name = event.plugin_name
        if not plugin_name:
            return
        if not self._deps.orchestrator.plugin_manager.is_known_plugin(plugin_name):
            logger.debug("Ignoring event for unknown or purged plugin '%s'.", plugin_name)
            return
        if event.new_state in (ORCH_STATE_STOPPED, PLUGIN_STATE_STOPPED):
            await self._deps.state.reset_plugin_runtime_state(plugin_name)

            def _clear_execution_tracking(state: PluginState) -> None:
                state.active_tasks.clear()
                state.is_busy = False
                state.finalize_pending = False

            await self._deps.state.update_plugin_state(plugin_name, _clear_execution_tracking)
            await self._deps.state.signal_finalize_complete(plugin_name)
            return
        if log_transition:
            logger.debug(
                "Director processing state change for %s: %s -> %s (by %s)",
                plugin_name,
                event.previous_state,
                event.new_state,
                event.authority,
            )
        plugin_instance = await self._deps.orchestrator.plugin_manager.get_plugin_instance(
            plugin_name,
        )
        is_persistent = bool(plugin_instance.PERSISTENT) if plugin_instance is not None else False
        if event.new_state in INTERRUPTIBLE_IDLE_STATES and (not is_persistent):
            prioritize = coerce_bool_flag(
                details.get("prioritize_for_eviction"),
                logger=logger,
                operation="orchestrator.lifecycle.watchers.coerce_bool_flag",
                default=False,
                recover_message="Failed to parse boolean flag (non-critical).",
            )
            await self._deps.state.set_idle_plugin(
                plugin_name,
                time.monotonic(),
                prioritize=prioritize,
            )
            if prioritize:
                logger.info(
                    "Plugin '%s' prioritized for eviction due to request cancellation.",
                    plugin_name,
                )
            return
        await self._deps.state.pop_idle_plugin(plugin_name)

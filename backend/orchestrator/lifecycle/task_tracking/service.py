"""SoAI - Task tracking service coordinating eviction and finalization [backend/orchestrator/lifecycle/task_tracking/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.logging.trace import get_logger
from core.orchestrator.protocols_lifecycle import PluginStateProtocol
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from core.state.state_transition_sets import DISPATCH_READY_STATES
from core.tasks.task import Task
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.types.json_value import copy_json_dict
from orchestrator.lifecycle.task_tracking.dependencies import TaskTrackingDependencies
from orchestrator.lifecycle.task_tracking.eviction import select_eviction_candidate
from orchestrator.lifecycle.task_tracking.finalization import transition_to_idle_state
from orchestrator.lifecycle.task_tracking.model_context import (
    write_task_configuration_log,
)
from orchestrator.lifecycle.task_tracking.param_matching import (
    check_reload_params_match,
)
from orchestrator.plugin_state import PluginState

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates
    from core.types.json import JSONDict, JSONValue

__all__ = ("OrchestratorLifecycleTaskTracking",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.service"


class OrchestratorLifecycleTaskTracking:
    def __init__(self, deps: TaskTrackingDependencies) -> None:
        self._deps = deps

    async def try_register_compatible_task_start(
        self,
        plugin_name: str,
        tracking_id: str,
        request_universal_id: str,
        request_startup_params: JSONDict,
        *,
        provider_backed: bool,
        persistent_runtime: bool,
    ) -> bool:
        if not await self._deps.state.wait_for_finalize_complete(
            plugin_name,
            LOCAL_IO_TIMEOUT_SEC,
        ):
            return False
        lifecycle = self._deps.orchestrator.plugin_manager.lifecycle
        async with lifecycle.plugin_lock_scope(plugin_name):
            ready_states = set(DISPATCH_READY_STATES)
            if provider_backed:
                ready_states.update(PROVIDER_BACKED_IGNORED_PLUGIN_STATES)
            plugin_status = await self._deps.orchestrator.state_aggregator.get_plugin_status(
                plugin_name,
            )
            if plugin_status not in ready_states:
                return False
            async with self._deps.state.plugins_context() as plugin_context:
                plugin_state = plugin_context.plugin_states.get(plugin_name)
                if plugin_state is None:
                    if not provider_backed and not persistent_runtime:
                        return False
                    loaded_universal_id = None
                    loaded_parameters = None
                    finalize_pending = False
                else:
                    loaded_universal_id = plugin_state.loaded_model_universal_id
                    loaded_parameters = (
                        copy_json_dict(plugin_state.loaded_parameters)
                        if plugin_state.loaded_parameters is not None
                        else None
                    )
                    finalize_pending = plugin_state.finalize_pending
            if finalize_pending:
                return False
            if (
                not provider_backed
                and not persistent_runtime
                and loaded_universal_id != request_universal_id
            ):
                return False
            if not persistent_runtime:
                if not await self.reload_params_match(
                    plugin_name,
                    loaded_parameters,
                    request_startup_params,
                ):
                    return False
            plugin_status = await self._deps.orchestrator.state_aggregator.get_plugin_status(
                plugin_name,
            )
            if plugin_status not in ready_states:
                return False
            async with self._deps.state.plugins_context() as plugin_context:
                plugin_state = plugin_context.plugin_states.get(plugin_name)
                if plugin_state is None:
                    if not provider_backed and not persistent_runtime:
                        return False
                    plugin_state = PluginState(plugin_name=plugin_name)
                    plugin_context.plugin_states[plugin_name] = plugin_state
                current_loaded_parameters = plugin_state.loaded_parameters
                loaded_parameters_unchanged = persistent_runtime or (
                    (current_loaded_parameters is None and loaded_parameters is None)
                    or (
                        current_loaded_parameters is not None
                        and loaded_parameters is not None
                        and current_loaded_parameters == loaded_parameters
                    )
                )
                if plugin_state.finalize_pending or not loaded_parameters_unchanged:
                    return False
                if (
                    not provider_backed
                    and not persistent_runtime
                    and plugin_state.loaded_model_universal_id != request_universal_id
                ):
                    return False
                plugin_state.active_tasks.add(tracking_id)
                plugin_state.last_request_universal_id = request_universal_id
                plugin_state.is_busy = True
                plugin_state.last_activity = time.monotonic()
                plugin_context.idle_plugins.pop(plugin_name, None)
                return True

    async def register_task_finish(
        self,
        plugin_name: str,
        tracking_id: str,
        *,
        duration: float | None,
        completed: bool,
        cancelled: bool,
        is_persistent: bool,
        last_task_id: str | None,
    ) -> None:
        should_finalize = False
        await self._deps.state.mark_finalize_started(plugin_name)
        try:
            async with self._deps.state.plugins_context() as plugin_context:
                plugin_state = plugin_context.plugin_states.get(plugin_name)
                if plugin_state is None:
                    return
                plugin_state.active_tasks.discard(tracking_id)
                plugin_state.last_activity = time.monotonic()
                if completed and duration is not None and duration > 0:
                    alpha = 0.2
                    plugin_state.avg_processing_time_ema = (duration * alpha) + (
                        plugin_state.avg_processing_time_ema * (1 - alpha)
                    )
                if not plugin_state.active_tasks:
                    plugin_state.is_busy = False
                    plugin_state.finalize_pending = True
                    should_finalize = True

            if should_finalize:
                try:
                    await self.finalize_idle_state(
                        plugin_name,
                        last_task_id=last_task_id,
                        cancelled=cancelled,
                        is_persistent_override=is_persistent,
                    )
                finally:
                    await uncancel_then_cleanup(
                        self._deps.state.clear_finalize_pending(plugin_name),
                    )
        finally:
            await uncancel_then_cleanup(self._deps.state.signal_finalize_complete(plugin_name))

    async def get_active_task_count(self, plugin_name: str) -> int:
        async with self._deps.state.plugins_context() as plugin_context:
            plugin_state = plugin_context.plugin_states.get(plugin_name)
            return len(plugin_state.active_tasks) if plugin_state is not None else 0

    async def finalize_idle_state(
        self,
        plugin_name: str,
        *,
        last_task_id: str | None = None,
        cancelled: bool = False,
        is_persistent_override: bool | None = None,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        await transition_to_idle_state(
            plugin_name,
            last_task_id=last_task_id,
            cancelled=cancelled,
            is_persistent_override=is_persistent_override,
            state=self._deps.state,
            state_aggregator=self._deps.orchestrator.state_aggregator,
            plugin_manager=self._deps.orchestrator.plugin_manager,
            model_parameter_service=self._deps.orchestrator.model_parameter_service,
            lifecycle_publisher=self._deps.lifecycle_publisher,
            shutdown_event=self._deps.shutdown_event,
            logger=logger,
        )

    async def log_task_configuration(self, task: Task, model_info: Mapping[str, JSONValue]) -> None:
        logger = get_logger(LOGGER_NAME)
        await write_task_configuration_log(
            task,
            model_info,
            param_manager=self._deps.orchestrator.param_manager,
            tool_name_extractor=self._deps.tool_name_extractor,
            logger=logger,
        )

    async def reload_params_match(
        self,
        plugin_name: str,
        loaded_params: JSONDict | None,
        request_params: JSONDict,
    ) -> bool:
        return await check_reload_params_match(
            plugin_name,
            loaded_params,
            request_params,
            self._deps.orchestrator.param_manager,
        )

    async def find_eviction_candidate(
        self,
        plugin_persistence: Mapping[str, bool],
        *,
        exclude: set[str] | None = None,
        all_states: ImmutablePluginStates | None = None,
        idle_plugins_snapshot: list[str] | None = None,
        plugin_states_snapshot: Mapping[str, PluginStateProtocol] | None = None,
        queue_empty_snapshot: Mapping[str, bool] | None = None,
    ) -> str | None:
        if all_states is None:
            all_states = await self._deps.orchestrator.state_aggregator.get_all_plugin_states()
        needs_state_snapshots = idle_plugins_snapshot is None or plugin_states_snapshot is None
        if needs_state_snapshots:
            async with self._deps.state.plugins_context() as plugin_context:
                if idle_plugins_snapshot is None:
                    idle_plugins_snapshot = list(plugin_context.idle_plugins)
                if plugin_states_snapshot is None:
                    plugin_states_snapshot = dict(plugin_context.plugin_states)
        if queue_empty_snapshot is None:
            queue_empty_snapshot = await self._deps.capacity.get_queue_empty_snapshot(
                list(all_states.keys()),
            )
        return select_eviction_candidate(
            plugin_persistence,
            exclude=exclude,
            all_states=all_states,
            idle_plugins_snapshot=idle_plugins_snapshot or [],
            plugin_states_snapshot=plugin_states_snapshot or {},
            queue_empty_snapshot=queue_empty_snapshot or {},
        )

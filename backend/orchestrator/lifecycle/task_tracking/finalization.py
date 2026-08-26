"""SoAI - Idle state finalization for task tracking [backend/orchestrator/lifecycle/task_tracking/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import await_publication_receipt
from core.logging.trace import TraceLogger
from core.models.protocols import ModelParameterServiceProtocol
from core.orchestrator.protocols_lifecycle import OrchestratorLifecyclePublisherProtocol
from core.plugins.protocols import PluginManagerProtocol
from core.state.protocols import StateAggregatorProtocol
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    PLUGIN_STATE_PERSISTENT_READY,
)
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict

__all__ = (
    "is_model_dirty",
    "transition_to_idle_state",
)

OPERATION_TRANSITION_TO_IDLE_STATE = (
    "orchestrator.lifecycle.task_tracking.finalization.transition_to_idle_state"
)


async def is_model_dirty(
    plugin_name: str,
    state: LifecycleStateAccessorProtocol,
    model_parameter_service: ModelParameterServiceProtocol,
) -> bool:
    async with state.plugins_context() as plugin_context:
        plugin_state = plugin_context.plugin_states.get(plugin_name)
        if plugin_state is None or not plugin_state.loaded_model_universal_id:
            return False
        loaded_universal_id = plugin_state.loaded_model_universal_id
        current_version = plugin_state.parameter_version
    _, latest_version = await model_parameter_service.model_get_parameters_and_version(
        loaded_universal_id,
    )
    return current_version != latest_version


async def transition_to_idle_state(
    plugin_name: str,
    *,
    last_task_id: str | None = None,
    cancelled: bool = False,
    is_persistent_override: bool | None = None,
    state: LifecycleStateAccessorProtocol,
    state_aggregator: StateAggregatorProtocol,
    plugin_manager: PluginManagerProtocol,
    model_parameter_service: ModelParameterServiceProtocol,
    lifecycle_publisher: OrchestratorLifecyclePublisherProtocol,
    shutdown_event: asyncio.Event,
    logger: TraceLogger,
) -> None:
    if shutdown_event.is_set():
        logger.trace("Skipping idle transition for '%s': shutdown is in progress.", plugin_name)
        return
    current_authoritative_state = await state_aggregator.get_plugin_status(plugin_name)
    if current_authoritative_state != ORCH_STATE_PROCESSING:
        return
    loaded_model_universal_id: str | None = None
    last_request_universal_id: str | None = None
    async with state.plugins_context() as plugin_context:
        plugin_state = plugin_context.plugin_states.get(plugin_name)
        if plugin_state is not None and plugin_state.active_tasks:
            logger.trace(
                "Aborting idle transition for '%s': %s active task(s) found during finalization check.",
                plugin_name,
                len(plugin_state.active_tasks),
            )
            return
        loaded_model_universal_id = (
            plugin_state.loaded_model_universal_id if plugin_state is not None else None
        )
        last_request_universal_id = (
            plugin_state.last_request_universal_id if plugin_state is not None else None
        )
    is_persistent = is_persistent_override
    inst = None
    if is_persistent is None:
        inst = await plugin_manager.get_plugin_instance(plugin_name)
        is_persistent = bool(inst.PERSISTENT) if inst is not None else False
    if (not loaded_model_universal_id) and (not is_persistent):
        raise ValidationError(
            "Loaded model universal_id missing during idle transition.",
            operation=OPERATION_TRANSITION_TO_IDLE_STATE,
            details={"plugin_name": plugin_name},
        )
    model_dirty = await is_model_dirty(plugin_name, state, model_parameter_service)
    new_state: PluginRuntimeStateName
    if is_persistent and cancelled:
        new_state = PLUGIN_STATE_PERSISTENT_READY
    elif model_dirty:
        new_state = ORCH_STATE_READY_DIRTY
    elif is_persistent:
        new_state = PLUGIN_STATE_PERSISTENT_READY
    else:
        new_state = ORCH_STATE_READY
    if is_persistent:
        if inst is None:
            inst = await plugin_manager.get_plugin_instance(plugin_name)
        if inst is None:
            new_state = ORCH_STATE_ERROR
            reason = (
                f"Persistent plugin instance missing after task {last_task_id}."
                if last_task_id
                else "Persistent plugin instance missing after task lifecycle completed."
            )
        else:
            try:
                health_task = create_ephemeral_task(
                    inst.health_ping(),
                    name=f"plugin-health-idle-finalization-{plugin_name}",
                    log_exceptions=False,
                )
                shutdown_task = create_ephemeral_task(
                    shutdown_event.wait(),
                    name=f"plugin-health-idle-shutdown-{plugin_name}",
                    log_exceptions=False,
                )
                done, _pending = await asyncio.wait(
                    {health_task, shutdown_task},
                    timeout=LOCAL_IO_TIMEOUT_SEC,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if shutdown_task in done or shutdown_event.is_set():
                    await cancel_and_await(
                        [health_task],
                        logger=logger,
                        task_label="persistent health validation",
                    )
                    return
                await cancel_and_await([shutdown_task], task_label="shutdown wait")
                if health_task not in done:
                    await cancel_and_await(
                        [health_task],
                        logger=logger,
                        task_label="persistent health validation",
                    )
                    raise TimeoutError("Persistent plugin health validation timed out.")
                healthy, health_message = health_task.result()
            except RECOVERABLE_EXCEPTIONS as exception:
                if shutdown_event.is_set():
                    return
                coerced_exception = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_TRANSITION_TO_IDLE_STATE,
                )
                log_exception(
                    logger,
                    coerced_exception,
                    message="Persistent plugin health validation failed during idle transition.",
                    operation=OPERATION_TRANSITION_TO_IDLE_STATE,
                    details={"plugin_name": plugin_name},
                )
                healthy = False
                health_message = coerced_exception.message
            if not healthy:
                new_state = ORCH_STATE_ERROR
                reason = (
                    f"Persistent plugin health validation failed after task {last_task_id}: {health_message}"
                    if last_task_id
                    else f"Persistent plugin health validation failed: {health_message}"
                )
            else:
                reason = (
                    f"Finished task {last_task_id}" if last_task_id else "Task lifecycle completed."
                )
    else:
        reason = f"Finished task {last_task_id}" if last_task_id else "Task lifecycle completed."
    logger.trace(
        "Plugin '%s' is now idle. Transitioning from PROCESSING to %s. Reason: %s",
        plugin_name,
        new_state,
        reason,
    )
    details: JSONDict = {}
    universal_id = loaded_model_universal_id or last_request_universal_id
    if universal_id:
        details["universal_id"] = universal_id
    if shutdown_event.is_set():
        logger.trace(
            "Skipping idle transition publish for '%s': shutdown is in progress.",
            plugin_name,
        )
        return
    receipt = await lifecycle_publisher.publish_runtime_state_change(
        plugin_name,
        new_state,
        reason,
        details=details,
        expected_previous_state=ORCH_STATE_PROCESSING,
        prioritize_for_eviction=cancelled,
    )
    await await_publication_receipt(receipt)

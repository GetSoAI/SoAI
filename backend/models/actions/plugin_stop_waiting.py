"""SoAI - Plugin stop coordination for model deletion [backend/models/actions/plugin_stop_waiting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.config.protocols import ConfigProtocol
from core.errors.status_mapping import error_type_to_status_code
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_plugins import ErrorEvent, RequestPluginStopAndWaitCommand
from core.events.types_tasks import TaskCompleteEvent
from core.runtime.protocols import RequestOwnershipContextProtocol
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_system_id, extend_soai_id
from core.state.protocols import StateAggregatorProtocol
from core.state.state_names import ORCH_STATE_STOPPING
from core.state.state_transition_sets import RUNTIME_TERMINATED_STATES
from core.tasks.api_events import send_task_complete_event, send_task_progress_event
from core.tasks.protocols import TaskRegistryProtocol
from core.timing.constants import FILE_LOCK_RETRY_INTERVAL_SEC
from models.actions.task_creation import (
    create_reply_bound_model_action_task,
    create_streaming_model_action_task,
)

__all__ = ("ensure_plugin_stopped_for_delete",)


async def ensure_plugin_stopped_for_delete(
    plugin_name: str,
    reply_channel: asyncio.Queue[Event],
    context: RequestOwnershipContextProtocol | None,
    state_aggregator: StateAggregatorProtocol,
    task_registry: TaskRegistryProtocol,
    event_bus: EventBusProtocol,
    config: ConfigProtocol,
) -> bool:
    current_status = await state_aggregator.get_plugin_status(plugin_name)
    if current_status in RUNTIME_TERMINATED_STATES:
        return True
    if current_status == ORCH_STATE_STOPPING:
        existing_stop_completed = await _wait_for_existing_stop_to_finish(
            plugin_name,
            reply_channel,
            state_aggregator,
            task_registry,
            config,
        )
        if existing_stop_completed is not None:
            return existing_stop_completed
    await create_reply_bound_model_action_task(
        task_registry,
        reply_channel,
        context,
        metadata={
            "operation": "ensure_plugin_stopped_for_delete",
            "plugin_name": plugin_name,
        },
    )
    await send_task_progress_event(
        reply_channel,
        percent=10,
        message="Plugin is loaded. Requesting stop...",
        registry=task_registry,
    )
    stop_task, stop_reply_queue, ownership = await create_streaming_model_action_task(
        task_registry,
        context,
        metadata={"operation": "request_plugin_stop", "plugin_name": plugin_name},
    )
    stop_trace_id = context.trace_id if context is not None else None
    client_ip_value = context.client_ip if context is not None else None
    if not stop_trace_id:
        stop_trace_id = create_system_id(
            subsystem="plugin_stop",
            owner=plugin_name,
            include_random_suffix=True,
        )
    else:
        stop_trace_id = extend_soai_id(stop_trace_id, ("plugin_stop",))
    stop_context = RequestContext(
        trace_id=stop_trace_id,
        client_ip=client_ip_value,
        user_id=ownership.user_id,
        task_id=stop_task.task_id,
        cancellation_id=stop_task.cancellation_id,
    )
    stop_command = RequestPluginStopAndWaitCommand(
        plugin_name=plugin_name,
        reply_channel=stop_reply_queue,
        request_source="model_deletion",
        context=stop_context,
    )
    await event_bus.publish(stop_command)
    stop_timeout = config.get_float("MODELS.ROUTING.HEALTH_CHECKS.COMMAND_TIMEOUTS_SEC.PLUGIN_STOP")
    try:
        async with asyncio.timeout(stop_timeout):
            while True:
                response = await stop_command.reply_channel.get()
                if isinstance(response, TaskCompleteEvent):
                    return await _handle_stop_completion(
                        response,
                        reply_channel,
                        task_registry,
                    )
                if isinstance(response, ErrorEvent):
                    await _send_stop_failure(
                        reply_channel,
                        task_registry,
                        message=response.message,
                        error_code=error_type_to_status_code(response.error_type),
                    )
                    return False
    except TimeoutError:
        await _send_stop_timeout_failure(reply_channel, task_registry)
        return False


async def _wait_for_existing_stop_to_finish(
    plugin_name: str,
    reply_channel: asyncio.Queue[Event],
    state_aggregator: StateAggregatorProtocol,
    task_registry: TaskRegistryProtocol,
    config: ConfigProtocol,
) -> bool | None:
    stop_timeout = config.get_float("MODELS.ROUTING.HEALTH_CHECKS.COMMAND_TIMEOUTS_SEC.PLUGIN_STOP")
    try:
        async with asyncio.timeout(stop_timeout):
            while True:
                current_status = await state_aggregator.get_plugin_status(plugin_name)
                if current_status in RUNTIME_TERMINATED_STATES:
                    return True
                if current_status != ORCH_STATE_STOPPING:
                    return None
                await asyncio.sleep(FILE_LOCK_RETRY_INTERVAL_SEC)
    except TimeoutError:
        await _send_stop_timeout_failure(reply_channel, task_registry)
        return False


async def _send_stop_timeout_failure(
    reply_channel: asyncio.Queue[Event],
    task_registry: TaskRegistryProtocol,
) -> None:
    await send_task_complete_event(
        reply_channel,
        "Cannot delete: Timed out waiting for plugin to stop.",
        success=False,
        error_code=504,
        registry=task_registry,
    )


async def _handle_stop_completion(
    response: TaskCompleteEvent,
    reply_channel: asyncio.Queue[Event],
    task_registry: TaskRegistryProtocol,
) -> bool:
    if response.success:
        return True
    await _send_stop_failure(
        reply_channel,
        task_registry,
        message=response.message,
        error_code=response.error_code or 500,
    )
    return False


async def _send_stop_failure(
    reply_channel: asyncio.Queue[Event],
    task_registry: TaskRegistryProtocol,
    *,
    message: str,
    error_code: int,
) -> None:
    await send_task_complete_event(
        reply_channel,
        f"Cannot delete: {message or 'Failed to stop plugin.'}",
        success=False,
        error_code=error_code,
        registry=task_registry,
    )

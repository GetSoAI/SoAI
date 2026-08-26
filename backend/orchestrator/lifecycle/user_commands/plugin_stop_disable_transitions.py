"""SoAI - Plugin stop and disable runtime transitions [backend/orchestrator/lifecycle/user_commands/plugin_stop_disable_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_STOPPED,
)
from core.tasks.api_events import send_task_complete_event, send_task_progress_event
from core.tasks.failure_events import send_error_event_and_finalize
from orchestrator.lifecycle.state_access.internal_protocols import (
    PluginWorkPurgeProtocol,
)
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)

__all__ = (
    "perform_stop_transition",
    "purge_plugin_work",
    "send_incompatible_disable_error",
    "send_missing_plugin_error",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.plugin_stop_disable_transitions"
OPERATION_CANCEL_START = "orchestrator.user_commands.cancel_scheduler_start"
STOP_TRANSITION_NOOP_STATES = frozenset(
    {
        ORCH_STATE_STOPPED,
        PLUGIN_STATE_BACKEND_NOT_INSTALLED,
        PLUGIN_STATE_INCOMPATIBLE,
        PLUGIN_STATE_NOT_DETECTED,
        PLUGIN_STATE_STOPPED,
    },
)


async def send_missing_plugin_error(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    reply_channel: asyncio.Queue[Event],
    plugin_name: str,
) -> None:
    await send_error_event_and_finalize(
        reply_channel,
        f"Plugin '{plugin_name}' not found.",
        ErrorType.NOT_FOUND,
        registry=deps.task_registry,
    )


async def send_incompatible_disable_error(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    reply_channel: asyncio.Queue[Event],
    plugin_name: str,
) -> None:
    display_name = await deps.orchestrator.plugin_manager.get_plugin_display_name(plugin_name)
    await send_error_event_and_finalize(
        reply_channel,
        (
            f"Cannot disable plugin '{display_name}'; it is incompatible with this SoAI "
            "version and must be removed."
        ),
        ErrorType.CONFLICT,
        registry=deps.task_registry,
    )


async def purge_plugin_work(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    plugin_name: str,
    command_name: str,
    completion_name: str,
    error_type: ErrorType,
    reply_channel: asyncio.Queue[Event],
    purge_plugin_requests: PluginWorkPurgeProtocol,
) -> None:
    await send_task_progress_event(
        reply_channel,
        registry=deps.task_registry,
        percent=10,
        message="Cancelling plugin work...",
    )
    await cancel_scheduler_start_for_stop(
        deps,
        plugin_name=plugin_name,
        completion_name=completion_name,
    )
    await purge_plugin_requests(
        plugin_name=plugin_name,
        purge_reason=f"Plugin '{plugin_name}' is being {completion_name}.",
        fail_reason=f"Plugin '{plugin_name}' was {completion_name} by an administrator.",
        error_type=error_type,
        operation=f"orchestrator.{command_name}_plugin",
    )
    await send_task_progress_event(
        reply_channel,
        registry=deps.task_registry,
        percent=40,
        message="Plugin work cancelled.",
    )


async def cancel_scheduler_start_for_stop(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    plugin_name: str,
    completion_name: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    timeout_sec = deps.orchestrator.config.get_float(
        "PLUGINS.STOP_START_TASK_CANCEL_TIMEOUT_SEC",
    )
    try:
        completed = await deps.orchestrator.scheduler_start_task_tracker.cancel_and_wait(
            plugin_name=plugin_name,
            cancellation_coordinator=deps.orchestrator.cancellation_coordinator,
            reason=f"Plugin '{plugin_name}' is being {completion_name}.",
            timeout_sec=timeout_sec,
            logger=logger,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to cancel scheduler start task before plugin stop.",
            operation=OPERATION_CANCEL_START,
            details={"plugin_name": plugin_name},
            level="warning",
        )
        return
    if not completed:
        logger.error(
            "Scheduler start task for plugin '%s' did not finish before stop continued.",
            plugin_name,
        )


async def perform_stop_transition(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    plugin_name: str,
    command_name: str,
    reply_channel: asyncio.Queue[Event],
) -> PluginStopOutcome:
    await send_task_progress_event(
        reply_channel,
        registry=deps.task_registry,
        percent=60,
        message="Stopping plugin...",
    )
    current_state = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
    if current_state in STOP_TRANSITION_NOOP_STATES:
        return PluginStopOutcome(
            terminated=True,
            message=f"Plugin '{plugin_name}' is already stopped.",
        )
    await publish_runtime_state_change_and_wait(
        publisher=deps.lifecycle_publisher,
        plugin_name=plugin_name,
        new_state=ORCH_STATE_STOPPING,
        reason=f"Plugin {command_name} requested by user.",
    )
    stop_outcome = await deps.shutdown.perform_plugin_stop_logic(plugin_name)
    if not stop_outcome.terminated:
        await publish_runtime_state_change_and_wait(
            publisher=deps.lifecycle_publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_ERROR,
            reason=stop_outcome.message or "Plugin stop process failed.",
        )
        await send_task_complete_event(
            reply_channel,
            stop_outcome.message or f"Plugin '{plugin_name}' could not be stopped.",
            success=False,
            error_code=500,
            registry=deps.task_registry,
        )
        return stop_outcome
    await publish_runtime_state_change_and_wait(
        publisher=deps.lifecycle_publisher,
        plugin_name=plugin_name,
        new_state=ORCH_STATE_STOPPED,
        reason="Plugin stop process completed.",
    )
    return stop_outcome

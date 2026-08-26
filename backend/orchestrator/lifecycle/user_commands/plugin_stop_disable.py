"""SoAI - Plugin stop and disable command policy [backend/orchestrator/lifecycle/user_commands/plugin_stop_disable.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.events.types_plugins import (
    RequestPluginDisableCommand,
    RequestPluginStopAndWaitCommand,
)
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_STOPPED,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_STOPPED,
)
from core.tasks.api_events import send_task_complete_event, send_task_progress_event
from orchestrator.lifecycle.state_access.internal_protocols import (
    PluginWorkPurgeProtocol,
)
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)
from orchestrator.lifecycle.user_commands.plugin_backend_cleanup import (
    cleanup_tracked_backend_processes_if_needed,
)
from orchestrator.lifecycle.user_commands.plugin_stop_disable_transitions import (
    perform_stop_transition,
    purge_plugin_work,
    send_incompatible_disable_error,
    send_missing_plugin_error,
)
from orchestrator.lifecycle.user_commands.runner import run_lifecycle_command

__all__ = (
    "handle_plugin_disable_command",
    "handle_plugin_stop_command",
)

STOP_NOOP_STATES = frozenset(
    {
        ORCH_STATE_STOPPED,
        PLUGIN_STATE_BACKEND_NOT_INSTALLED,
        PLUGIN_STATE_INCOMPATIBLE,
        PLUGIN_STATE_NOT_DETECTED,
        PLUGIN_STATE_STOPPED,
    },
)
DISABLE_SKIP_STOP_STATES = frozenset(
    {
        ORCH_STATE_STOPPED,
        PLUGIN_STATE_BACKEND_NOT_INSTALLED,
        PLUGIN_STATE_NOT_DETECTED,
        PLUGIN_STATE_STOPPED,
    },
)


async def handle_plugin_stop_command(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    command: RequestPluginStopAndWaitCommand,
    purge_plugin_requests: PluginWorkPurgeProtocol,
) -> None:
    plugin_name = command.plugin_name
    error_type = (
        ErrorType.MODEL_DELETED
        if command.request_source == "model_deletion"
        else ErrorType.MODEL_STOPPED
    )

    async def handler() -> None:
        if not deps.orchestrator.plugin_manager.is_known_plugin(plugin_name):
            await send_missing_plugin_error(
                deps,
                reply_channel=command.reply_channel,
                plugin_name=plugin_name,
            )
            return
        current_state = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
        if current_state == ORCH_STATE_DISABLED:
            if not await cleanup_tracked_backend_processes_if_needed(
                deps,
                plugin_name=plugin_name,
                reply_channel=command.reply_channel,
                command_name="stop",
            ):
                return
            await purge_plugin_work(
                deps,
                plugin_name=plugin_name,
                command_name="stop",
                completion_name="stopped",
                error_type=error_type,
                reply_channel=command.reply_channel,
                purge_plugin_requests=purge_plugin_requests,
            )
            await send_task_complete_event(
                command.reply_channel,
                f"Plugin '{plugin_name}' is already disabled.",
                registry=deps.task_registry,
            )
            return
        if current_state in STOP_NOOP_STATES:
            if not await cleanup_tracked_backend_processes_if_needed(
                deps,
                plugin_name=plugin_name,
                reply_channel=command.reply_channel,
                command_name="stop",
            ):
                return
            await purge_plugin_work(
                deps,
                plugin_name=plugin_name,
                command_name="stop",
                completion_name="stopped",
                error_type=error_type,
                reply_channel=command.reply_channel,
                purge_plugin_requests=purge_plugin_requests,
            )
            await send_task_complete_event(
                command.reply_channel,
                f"Plugin '{plugin_name}' is already stopped.",
                registry=deps.task_registry,
            )
            return
        await purge_plugin_work(
            deps,
            plugin_name=plugin_name,
            command_name="stop",
            completion_name="stopped",
            error_type=error_type,
            reply_channel=command.reply_channel,
            purge_plugin_requests=purge_plugin_requests,
        )
        stop_outcome = await perform_stop_transition(
            deps,
            plugin_name=plugin_name,
            command_name="stop",
            reply_channel=command.reply_channel,
        )
        if stop_outcome.terminated:
            await send_task_complete_event(
                command.reply_channel,
                f"Plugin '{plugin_name}' has been stopped.",
                registry=deps.task_registry,
            )

    await run_lifecycle_command(
        deps,
        plugin_name=plugin_name,
        command=command,
        action_name="Stop",
        handler=handler,
    )


async def handle_plugin_disable_command(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    command: RequestPluginDisableCommand,
    purge_plugin_requests: PluginWorkPurgeProtocol,
) -> None:
    plugin_name = command.plugin_name

    async def handler() -> None:
        if not deps.orchestrator.plugin_manager.is_known_plugin(plugin_name):
            await send_missing_plugin_error(
                deps,
                reply_channel=command.reply_channel,
                plugin_name=plugin_name,
            )
            return
        current_state = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
        if current_state == PLUGIN_STATE_INCOMPATIBLE:
            await send_incompatible_disable_error(
                deps,
                reply_channel=command.reply_channel,
                plugin_name=plugin_name,
            )
            return
        if current_state == ORCH_STATE_DISABLED:
            if not await cleanup_tracked_backend_processes_if_needed(
                deps,
                plugin_name=plugin_name,
                reply_channel=command.reply_channel,
                command_name="disable",
            ):
                return
            await purge_plugin_work(
                deps,
                plugin_name=plugin_name,
                command_name="disable",
                completion_name="disabled",
                error_type=ErrorType.MODEL_STOPPED,
                reply_channel=command.reply_channel,
                purge_plugin_requests=purge_plugin_requests,
            )
            await send_task_complete_event(
                command.reply_channel,
                f"Plugin '{plugin_name}' is already disabled.",
                registry=deps.task_registry,
            )
            return
        await purge_plugin_work(
            deps,
            plugin_name=plugin_name,
            command_name="disable",
            completion_name="disabled",
            error_type=ErrorType.MODEL_STOPPED,
            reply_channel=command.reply_channel,
            purge_plugin_requests=purge_plugin_requests,
        )
        if current_state not in DISABLE_SKIP_STOP_STATES:
            stop_outcome = await perform_stop_transition(
                deps,
                plugin_name=plugin_name,
                command_name="disable",
                reply_channel=command.reply_channel,
            )
            if not stop_outcome.terminated:
                return
        elif not await cleanup_tracked_backend_processes_if_needed(
            deps,
            plugin_name=plugin_name,
            reply_channel=command.reply_channel,
            command_name="disable",
        ):
            return
        await send_task_progress_event(
            command.reply_channel,
            registry=deps.task_registry,
            percent=85,
            message="Disabling plugin...",
        )
        await publish_runtime_state_change_and_wait(
            publisher=deps.lifecycle_publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_DISABLED,
            reason="Plugin manually disabled by user.",
        )
        await send_task_complete_event(
            command.reply_channel,
            f"Plugin '{plugin_name}' has been disabled.",
            registry=deps.task_registry,
        )

    await run_lifecycle_command(
        deps,
        plugin_name=plugin_name,
        command=command,
        action_name="Disable",
        handler=handler,
    )

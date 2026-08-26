"""SoAI - Plugin enable user command handler [backend/orchestrator/lifecycle/user_commands/plugin_enable.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import RequestPluginEnableCommand
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN,
    SchedulerWorkItem,
)
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PluginRuntimeStateName,
)
from core.tasks.api_events import send_task_complete_event
from core.tasks.failure_events import send_error_event_and_finalize
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)
from orchestrator.lifecycle.user_commands.plugin_activation_resolution import (
    resolve_plugin_activation_transition,
)
from orchestrator.lifecycle.user_commands.runner import run_lifecycle_command

__all__ = ("handle_plugin_enable_command",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.plugin_enable"
OPERATION = "orchestrator.handle_plugin_enable_command"
ACTIVATION_OPERATION = "orchestrator.handle_plugin_enable_command.persistent"
BASE_REASON = "Plugin re-enabled by user."


async def handle_plugin_enable_command(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    command: RequestPluginEnableCommand,
) -> list[SchedulerWorkItem]:
    plugin_name = command.plugin_name

    async def handler() -> SchedulerWorkItem | None:
        logger = get_logger(LOGGER_NAME)
        if (
            await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
            != ORCH_STATE_DISABLED
        ):
            await send_error_event_and_finalize(
                command.reply_channel,
                f"Plugin '{plugin_name}' is not disabled.",
                ErrorType.INVALID_REQUEST,
                registry=deps.task_registry,
            )
            return None
        transition = await resolve_plugin_activation_transition(
            plugin_manager=deps.orchestrator.plugin_manager,
            plugin_name=plugin_name,
            attempt_activate=True,
            failure_state=ORCH_STATE_ERROR,
            operation=ACTIVATION_OPERATION,
            logger=logger,
            base_reason=BASE_REASON,
        )
        target_state: PluginRuntimeStateName = transition.target_state
        reason = transition.reason
        completion_message = f"Plugin '{plugin_name}' enabled and available to scheduler."
        if target_state == PLUGIN_STATE_BACKEND_NOT_INSTALLED:
            completion_message = (
                f"Plugin '{plugin_name}' enabled, but its backend is not installed."
            )
        elif target_state == ORCH_STATE_ERROR:
            completion_message = (
                f"Plugin '{plugin_name}' enabled, but its backend failed health validation."
            )
        await deps.lifecycle_publisher.publish_runtime_state_change(
            plugin_name,
            target_state,
            reason,
        )
        try:
            await deps.orchestrator.database_plugins.mark_plugin_user_enabled_once(plugin_name)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Failed to persist user enablement state for '{plugin_name}'",
                operation=OPERATION,
            )
        await send_task_complete_event(
            command.reply_channel,
            completion_message,
            registry=deps.task_registry,
        )
        return SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)

    result = await run_lifecycle_command(
        deps,
        plugin_name=plugin_name,
        command=command,
        action_name="Enable",
        handler=handler,
    )
    return [result] if result else []

"""SoAI - Lifecycle lock coordination and state guards [backend/orchestrator/lifecycle/user_commands/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import ReplyableCommand
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_INSTALLING,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_REMOVING_BACKEND,
)
from core.tasks.failure_events import send_error_event_and_finalize
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)

__all__ = (
    "reject_user_command_if_prohibitive_state",
    "run_lifecycle_command",
)

OPERATION_ORCHESTRATOR_LIFECYCLE_USER_COMMANDS_RUNNER_RUN_LIFECYCLE_COMMAND = (
    "orchestrator.lifecycle.user_commands.runner.run_lifecycle_command"
)


LOGGER_NAME = "SoAI.orchestrator.lifecycle.runner"


async def reject_user_command_if_prohibitive_state(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    plugin_name: str,
    command: ReplyableCommand,
    action_name: str,
) -> bool:
    current_state = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
    if current_state not in {
        PLUGIN_STATE_DELETING,
        PLUGIN_STATE_REMOVING_BACKEND,
        PLUGIN_STATE_BACKEND_INSTALLING,
    }:
        return False
    display_name = await deps.orchestrator.plugin_manager.get_plugin_display_name(plugin_name)
    error_message = f"{action_name} for '{display_name}' rejected. Plugin in prohibitive state: '{current_state}'."
    await send_error_event_and_finalize(
        command.reply_channel,
        error_message,
        ErrorType.CONFLICT,
        registry=deps.task_registry,
    )
    return True


async def run_lifecycle_command(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    plugin_name: str,
    command: ReplyableCommand,
    action_name: str,
    handler: Callable[[], Awaitable[SchedulerWorkItem | None]],
) -> SchedulerWorkItem | None:
    logger = get_logger(LOGGER_NAME)
    rejected = await reject_user_command_if_prohibitive_state(
        deps,
        plugin_name=plugin_name,
        command=command,
        action_name=action_name,
    )
    if rejected:
        return None
    try:
        return await handler()
    except RECOVERABLE_EXCEPTIONS as exception:
        operation = action_name.lower()
        log_exception(
            logger,
            exception,
            message=f"Error {operation} plugin {plugin_name}",
            operation=OPERATION_ORCHESTRATOR_LIFECYCLE_USER_COMMANDS_RUNNER_RUN_LIFECYCLE_COMMAND,
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            f"Failed to {operation} plugin: {exception}",
            ErrorType.SERVER_ERROR,
            registry=deps.task_registry,
        )
        return None

"""SoAI - Background scheduling for plugin lifecycle commands [backend/orchestrator/control/plugin_lifecycle_command_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_plugins import (
    ClearQuarantineCommand,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
)
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.api_events import send_task_complete_event
from core.tasks.failure_events import send_error_event_and_finalize
from orchestrator.control.plugin_command_dependencies import (
    OrchestratorPluginCommandDependencies,
)
from orchestrator.control.plugin_command_rejection import (
    reject_user_command_if_invalid_state,
)
from orchestrator.control.plugin_scheduler_work import schedule_work_items

__all__ = (
    "schedule_clear_quarantine_task",
    "schedule_plugin_disable_task",
    "schedule_plugin_enable_task",
    "schedule_plugin_stop_task",
)

OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_LIFECYCLE_TASKS_GUARDED_RUNNER = (
    "orchestrator.control.plugin_lifecycle_command_tasks.guarded_runner"
)
OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_LIFECYCLE_TASKS_SPAWN_PLUGIN_COMMAND_TASK = (
    "orchestrator.control.plugin_lifecycle_command_tasks.spawn_plugin_command_task"
)


LOGGER_NAME = "SoAI.orchestrator.control.plugin_lifecycle_command_tasks"


async def schedule_plugin_stop_task(
    command: RequestPluginStopAndWaitCommand,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if await _reject_user_command_if_invalid_state(
        command=command,
        deps=deps,
        action_name="Stop",
        requires_plugin_lock=command.request_source == "model_deletion",
    ):
        return
    await _spawn_plugin_command_task(
        plugin_name=command.plugin_name,
        command_name="stop",
        reply_channel=command.reply_channel,
        deps=deps,
        runner=lambda: deps.lifecycle.user_commands.handle_plugin_stop_command(command),
    )


async def schedule_plugin_disable_task(
    command: RequestPluginDisableCommand,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if await _reject_user_command_if_invalid_state(
        command=command,
        deps=deps,
        action_name="Disable",
    ):
        return
    await _spawn_plugin_command_task(
        plugin_name=command.plugin_name,
        command_name="disable",
        reply_channel=command.reply_channel,
        deps=deps,
        runner=lambda: deps.lifecycle.user_commands.handle_plugin_disable_command(command),
    )


async def schedule_plugin_enable_task(
    command: RequestPluginEnableCommand,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    await _spawn_plugin_command_task(
        plugin_name=command.plugin_name,
        command_name="enable",
        reply_channel=command.reply_channel,
        deps=deps,
        runner=lambda: deps.lifecycle.user_commands.handle_plugin_enable_command(command),
        scheduler_operation="orchestrator_control.handle_plugin_enable_command",
    )


async def schedule_clear_quarantine_task(
    command: ClearQuarantineCommand,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    await _spawn_plugin_command_task(
        plugin_name=command.plugin_name,
        command_name="clear_quarantine",
        reply_channel=command.reply_channel,
        deps=deps,
        runner=lambda: deps.lifecycle.user_commands.handle_clear_quarantine(command),
        scheduler_operation="orchestrator_control.handle_clear_quarantine",
    )


async def _reject_user_command_if_invalid_state(
    *,
    command: RequestPluginStopAndWaitCommand | RequestPluginDisableCommand,
    deps: OrchestratorPluginCommandDependencies,
    action_name: str,
    requires_plugin_lock: bool = False,
) -> bool:
    return await reject_user_command_if_invalid_state(
        orchestrator=deps.orchestrator,
        guardian_ref=deps.guardian_ref,
        task_registry=deps.task_registry,
        plugin_name=command.plugin_name,
        command=command,
        action_name=action_name,
        requires_plugin_lock=requires_plugin_lock,
    )


async def _spawn_plugin_command_task(
    *,
    plugin_name: str,
    command_name: str,
    reply_channel: asyncio.Queue[Event],
    deps: OrchestratorPluginCommandDependencies,
    runner: Callable[[], Awaitable[None | Sequence[SchedulerWorkItem]]],
    scheduler_operation: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    operation = f"orchestrator.control.plugin_{command_name}"

    async def guarded_runner() -> None:
        try:
            work_items = await runner()
            if scheduler_operation is not None and work_items is not None:
                await schedule_work_items(
                    scheduler=deps.scheduler,
                    work_items=work_items,
                    operation=scheduler_operation,
                )
        except asyncio.CancelledError:
            if not await _reply_task_is_terminal(reply_channel, deps=deps):
                await send_task_complete_event(
                    reply_channel,
                    f"Plugin {command_name} command for '{plugin_name}' was cancelled.",
                    cancelled=True,
                    registry=deps.task_registry,
                )
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if await _reply_task_is_terminal(reply_channel, deps=deps):
                return
            log_exception(
                logger,
                exception,
                message=f"Failed to execute plugin {command_name} command.",
                operation=OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_LIFECYCLE_TASKS_GUARDED_RUNNER,
                details={"plugin_name": plugin_name, "operation": operation},
                level="warning",
            )
            await send_error_event_and_finalize(
                reply_channel,
                f"Failed to {command_name} plugin '{plugin_name}'.",
                ErrorType.SERVER_ERROR,
                registry=deps.task_registry,
            )

    scheduled_runner = guarded_runner()
    try:
        _ = await deps.spawn_background_task(
            coro=scheduled_runner,
            owner=f"orchestrator_plugin_{command_name}",
            metadata={"plugin_name": plugin_name, "operation": operation},
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "orchestrator",
                    "plugin_command",
                    safe_or_hashed_segment(str(command_name)),
                    safe_or_hashed_segment(plugin_name),
                ),
            ),
            name=f"orchestrator-plugin-{command_name}-{plugin_name}",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        scheduled_runner.close()
        log_exception(
            logger,
            exception,
            message=f"Failed to schedule plugin {command_name} command.",
            operation=OPERATION_ORCHESTRATOR_CONTROL_PLUGIN_LIFECYCLE_TASKS_SPAWN_PLUGIN_COMMAND_TASK,
            details={"plugin_name": plugin_name, "operation": operation},
            level="warning",
        )
        await send_error_event_and_finalize(
            reply_channel,
            f"Failed to {command_name} plugin '{plugin_name}': {exception}",
            ErrorType.SERVER_ERROR,
            registry=deps.task_registry,
        )


async def _reply_task_is_terminal(
    reply_channel: asyncio.Queue[Event],
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> bool:
    identity = deps.task_registry.resolve_task_identity_for_reply_queue(reply_channel)
    if identity is None:
        return False
    task = await deps.task_registry.get(identity[0])
    return task is not None and task.status.is_terminal()

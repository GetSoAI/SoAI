"""SoAI - Plugin backend lifecycle command handlers [backend/plugins/actions/backend_lifecycle_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import (
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from core.logging.trace import get_logger
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.errors import TaskIDCollisionError
from plugins.actions.backend_lifecycle_execution import execute_lifecycle_task
from plugins.actions.backend_lifecycle_stop import stop_plugin_if_running
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.actions.progress import send_completion_with_task
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.manager.backend_variant_counts import refresh_backend_variant_count
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.task_collisions import handle_plugin_manager_task_id_collision

if TYPE_CHECKING:
    import asyncio

    from core.events.types_base import Event
    from core.types.json import JSONDict

__all__ = (
    "process_install_command_async",
    "process_remove_command_async",
    "process_update_command_async",
)

LOGGER_NAME = "SoAI.plugins.actions.backend_lifecycle_commands"
OPERATION = "plugin_flow.process_backend_action_async"
OPERATION_BACKEND_VARIANT_COUNT_REFRESH_AFTER_REMOVE = (
    "plugin_flow.process_backend_action_async.refresh_backend_variant_count_after_remove"
)


def _build_stop_running_plugin_pre_execute_hook(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    reply_channel: asyncio.Queue[Event] | None,
) -> Callable[[str | None, str], Awaitable[None]]:
    def pre_execute_hook(
        task_id: str | None,
        current_cancellation_id: str,
    ) -> Coroutine[None, None, None]:
        excluded_cancellation_ids = {current_cancellation_id}
        if isinstance(task_id, str) and task_id.strip():
            excluded_cancellation_ids.add(task_id.strip())
        return stop_plugin_if_running(
            manager,
            plugin_name,
            reply_channel,
            task_id=task_id,
            exclude_cancellation_ids=frozenset(excluded_cancellation_ids),
        )

    return pre_execute_hook


async def _process_backend_action_async(
    manager: PluginManagerRuntimeProtocol,
    command: InstallPluginBackendCommand | UpdatePluginBackendCommand | RemovePluginBackendCommand,
    action_name: str,
    capability_error_message: str,
    display_name: str | None = None,
    pre_execute_hook: Callable[[str | None, str], Awaitable[None]] | None = None,
    task_id: str | None = None,
    current_cancellation_id: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    plugin_name, reply_channel = (command.plugin_name, command.reply_channel)
    resolved_display_name = display_name or await manager.get_plugin_display_name(plugin_name)
    mutation_fencing_token = (
        command.context.mutation_fencing_token if command.context is not None else None
    )
    action_succeeded = False
    async with serialized_plugin_load_scope(manager, plugin_name):
        try:
            if task_id is not None:
                persisted_task = await manager.dependencies.infrastructure.task_registry.get(
                    task_id,
                    force_refresh=True,
                )
                if persisted_task is not None and persisted_task.status.is_terminal():
                    return
            if not await validate_action_for_state_async(
                manager,
                plugin_name,
                action_name,
                reply_channel,
                task_id,
                mutation_fencing_token=mutation_fencing_token,
            ):
                return
            instance = await manager.require_loaded_plugin(plugin_name, auto_load=True)
            try:
                manager.require_plugin_capability(
                    instance,
                    "SUPPORTS_BACKEND_INSTALLATION",
                    f"Plugin '{resolved_display_name}' {capability_error_message}.",
                )
            except ValidationError as capability_error:
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=False,
                    message=str(capability_error),
                    mutation_fencing_token=mutation_fencing_token,
                    task_registry=manager.dependencies.infrastructure.task_registry,
                    send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
                return
            if pre_execute_hook:
                await pre_execute_hook(
                    task_id,
                    require_cancellation_id(current_cancellation_id),
                )
            action_succeeded = await execute_lifecycle_task(
                manager,
                command,
                action_name,
                task_id=task_id,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Error during {action_name} command",
                operation=OPERATION,
                details={"action": action_name, "plugin": resolved_display_name},
            )
            await send_completion_with_task(
                reply_channel,
                task_id,
                success=False,
                message=f"Failed to process {action_name} command: {exception}",
                mutation_fencing_token=mutation_fencing_token,
                task_registry=manager.dependencies.infrastructure.task_registry,
                send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
            )
    if action_succeeded and action_name == "remove_backend":
        try:
            await refresh_backend_variant_count(
                manager,
                plugin_name,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to refresh backend variant count after backend removal.",
                operation=OPERATION_BACKEND_VARIANT_COUNT_REFRESH_AFTER_REMOVE,
                details={"plugin_name": plugin_name},
                level="warning",
            )


async def _run_backend_lifecycle_command(
    manager: PluginManagerRuntimeProtocol,
    command: InstallPluginBackendCommand | UpdatePluginBackendCommand | RemovePluginBackendCommand,
    *,
    action_name: str,
    capability_error_message: str,
    metadata: JSONDict | None = None,
    pre_execute_hook: Callable[[str | None, str], Awaitable[None]] | None = None,
) -> None:
    plugin_name = command.plugin_name
    context = command.context
    reply_channel = command.reply_channel
    user_id = context.user_id if context else 0
    task_id_value = None
    if context:
        try:
            task_id_value = context.task_id
        except AttributeError:
            task_id_value = None
    display_name = await manager.get_plugin_display_name(plugin_name)
    lifecycle_metadata: JSONDict = {
        "operation": action_name,
        "display_name": display_name,
        "plugin": plugin_name,
    }
    if isinstance(command, InstallPluginBackendCommand | UpdatePluginBackendCommand):
        if command.backend_variant_id is not None:
            lifecycle_metadata["backend_variant_id"] = command.backend_variant_id
    if metadata:
        lifecycle_metadata.update(metadata)
    try:
        async with plugin_lifecycle_advisory_lock(
            manager,
            plugin_name,
            mutation_task_id=task_id_value,
            mutation_fencing_token=(
                context.mutation_fencing_token if context is not None else None
            ),
        ):
            async with manager.dependencies.infrastructure.lifecycle.lifecycle_scope(
                service_name="Plugin manager",
                task_type=action_name,
                plugin_name=plugin_name,
                metadata=lifecycle_metadata,
                acquire_plugin_lock=True,
                user_id=user_id,
                task_id=task_id_value,
                context=context,
            ) as (token, task_id):
                await _process_backend_action_async(
                    manager,
                    command,
                    action_name,
                    capability_error_message,
                    display_name,
                    pre_execute_hook=pre_execute_hook,
                    task_id=task_id,
                    current_cancellation_id=token.cancellation_id,
                )
    except TaskIDCollisionError as exception:
        await handle_plugin_manager_task_id_collision(manager, exception, reply_channel)


async def process_install_command_async(
    manager: PluginManagerRuntimeProtocol,
    command: InstallPluginBackendCommand,
) -> None:
    manager.require_online_mode("install plugin backends")
    if command.backend_variant_id is None:
        command.backend_variant_id = await manager.snapshot_backend_variant_selection(
            command.plugin_name,
        )
    await _run_backend_lifecycle_command(
        manager,
        command,
        action_name="install_backend",
        capability_error_message="does not support backend installation",
    )


async def process_update_command_async(
    manager: PluginManagerRuntimeProtocol,
    command: UpdatePluginBackendCommand,
) -> None:
    manager.require_online_mode("update plugin backends")
    if command.backend_variant_id is None:
        command.backend_variant_id = await manager.snapshot_backend_variant_selection(
            command.plugin_name,
        )
    await _run_backend_lifecycle_command(
        manager,
        command,
        action_name="update_backend",
        capability_error_message="does not support backend updates",
        pre_execute_hook=_build_stop_running_plugin_pre_execute_hook(
            manager,
            command.plugin_name,
            command.reply_channel,
        ),
    )


async def process_remove_command_async(
    manager: PluginManagerRuntimeProtocol,
    command: RemovePluginBackendCommand,
) -> None:
    await _run_backend_lifecycle_command(
        manager,
        command,
        action_name="remove_backend",
        capability_error_message="does not support backend removal",
        metadata={"delete_models": bool(command.delete_models)},
        pre_execute_hook=_build_stop_running_plugin_pre_execute_hook(
            manager,
            command.plugin_name,
            command.reply_channel,
        ),
    )

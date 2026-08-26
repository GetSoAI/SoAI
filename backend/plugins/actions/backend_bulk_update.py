"""SoAI - Bulk plugin backend update command processor [backend/plugins/actions/backend_bulk_update.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import (
    UpdateAllPluginBackendsCommand,
    UpdatePluginBackendCommand,
)
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.progress.percent import scale_percent_range
from core.runtime.request_context import RequestContext
from core.tasks.errors import TaskIDCollisionError
from core.validation.boolean_coercion import coerce_bool_with_recovery
from plugins.actions.backend_lifecycle_execution import execute_lifecycle_task
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.actions.progress import (
    notify_operation_cancelled,
    send_completion_with_task,
    send_progress_with_task,
    send_unexpected_error_completion_for_plugin_manager,
)
from plugins.context_ids import (
    resolve_task_id_from_context,
    resolve_user_id_from_context,
)
from plugins.manager.load_serialization import serialized_plugin_load_scope
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.task_collisions import handle_plugin_manager_task_id_collision

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.types.json import JSONValue

__all__ = ()

LOGGER_NAME = "SoAI.plugins.actions.backend_bulk_update"
OPERATION_PLUGIN_FLOW_PROCESS_UPDATE_ALL_BACKENDS_ASYNC = (
    "plugin_flow.process_update_all_backends_async"
)
OPERATION_PLUGIN_FLOW_PROCESS_UPDATE_ALL_BACKENDS_ASYNC_PREFLIGHT = (
    "plugin_flow.process_update_all_backends_async.preflight"
)


def _resolve_plugins_to_update(updates_available: Mapping[str, JSONValue]) -> list[str]:
    plugins: list[str] = []
    for name, status in updates_available.items():
        if not isinstance(status, dict):
            continue
        if coerce_bool_with_recovery(
            status,
            "update_available",
            logger=get_logger(LOGGER_NAME),
            operation="plugins.actions.backend_bulk_update.coerce_update_available_flag",
            default=False,
            recover_message="Failed to parse update_available flag (non-critical).",
        ):
            plugins.append(name)
    return plugins


def _build_progress_mapper(*, start_percent: int, end_percent: int) -> Callable[[int], int]:
    def progress_mapper(value: int) -> int:
        return scale_percent_range(
            value=value,
            start_percent=start_percent,
            end_percent=end_percent,
        )

    return progress_mapper


async def _update_single_backend(
    *,
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    display_name: str,
    reply_channel: asyncio.Queue[Event],
    task_id: str,
    context: RequestContext | None,
    start_percent: int,
    end_percent: int,
    logger: LoggerProtocol,
) -> bool:
    progress_mapper = _build_progress_mapper(
        start_percent=start_percent,
        end_percent=end_percent,
    )
    backend_variant_id = await manager.snapshot_backend_variant_selection(plugin_name)
    async with serialized_plugin_load_scope(manager, plugin_name):
        allowed = await validate_action_for_state_async(
            manager,
            plugin_name,
            "update_backend",
            reply_channel,
            task_id=task_id,
            emit_error_event=False,
            finalize_task=False,
        )
        if not allowed:
            await send_progress_with_task(
                reply_channel,
                task_id,
                start_percent,
                f"Skipping update for {display_name}: not allowed in current state.",
                manager.dependencies.infrastructure.task_registry,
                manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
            )
            return False
        try:
            await manager.ensure_system_capabilities(
                plugin_name,
                "Backend Update",
                action_key="update_backend",
            )
            instance = await manager.require_loaded_plugin(plugin_name, auto_load=True)
            manager.require_plugin_capability(
                instance,
                "SUPPORTS_BACKEND_INSTALLATION",
                f"Plugin '{display_name}' does not support backend updates.",
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Bulk update preflight failed",
                operation=OPERATION_PLUGIN_FLOW_PROCESS_UPDATE_ALL_BACKENDS_ASYNC_PREFLIGHT,
                details={"plugin": display_name},
            )
            await send_progress_with_task(
                reply_channel,
                task_id,
                start_percent,
                f"Skipping update for {display_name}: {exception}",
                manager.dependencies.infrastructure.task_registry,
                manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
            )
            return False
        update_cmd = UpdatePluginBackendCommand(
            plugin_name=plugin_name,
            backend_variant_id=backend_variant_id,
            reply_channel=reply_channel,
            context=context,
        )
        result = await execute_lifecycle_task(
            manager,
            update_cmd,
            "update_backend",
            send_completion_event=False,
            task_id=task_id,
            progress_mapper=progress_mapper,
        )
        await send_progress_with_task(
            reply_channel,
            task_id,
            end_percent,
            f"--- Completed update for {display_name} ---",
            manager.dependencies.infrastructure.task_registry,
            manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
        )
        return result


async def process_update_all_backends_async(
    manager: PluginManagerRuntimeProtocol,
    command: UpdateAllPluginBackendsCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    reply_channel, context = (command.reply_channel, command.context)
    user_id = resolve_user_id_from_context(context)
    task_id_value = resolve_task_id_from_context(context)
    try:
        async with manager.dependencies.infrastructure.lifecycle.lifecycle_scope(
            service_name="Plugin manager",
            task_type="update_all_backends",
            user_id=user_id,
            task_id=task_id_value,
            context=context,
        ) as (_, task_id):
            try:
                manager.require_online_mode("update all plugin backends")
                updates_available = await manager.check_for_backend_updates()
                plugins_to_update = _resolve_plugins_to_update(updates_available)
                if not plugins_to_update:
                    logger.info(
                        "Update-all-backends command completed: all plugin backends already up-to-date.",
                    )
                    await send_completion_with_task(
                        reply_channel,
                        task_id,
                        success=True,
                        message="All plugin backends are up-to-date.",
                        task_registry=manager.dependencies.infrastructure.task_registry,
                        send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                    )
                    return
                display_name_map = await manager.get_plugin_display_names(plugins_to_update)
                display_names = [
                    display_name_map.get(plugin, plugin) for plugin in plugins_to_update
                ]
                await send_progress_with_task(
                    reply_channel,
                    task_id,
                    0,
                    f"Starting update for {len(plugins_to_update)} plugins: {', '.join(display_names)}",
                    manager.dependencies.infrastructure.task_registry,
                    manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
                )
                all_tasks_successful = True
                total = len(plugins_to_update)
                for plugin_index, plugin_name in enumerate(plugins_to_update):
                    display_name = display_name_map.get(plugin_name, plugin_name)
                    start_percent = int(plugin_index * 100 / total) if total else 0
                    end_percent = (
                        100
                        if plugin_index == total - 1
                        else max(start_percent, int((plugin_index + 1) * 100 / total))
                    )
                    result = await _update_single_backend(
                        manager=manager,
                        plugin_name=plugin_name,
                        display_name=display_name,
                        reply_channel=reply_channel,
                        task_id=task_id,
                        context=context,
                        start_percent=start_percent,
                        end_percent=end_percent,
                        logger=logger,
                    )
                    if not result:
                        all_tasks_successful = False
                final_message = f"All plugin backend updates attempted.{(' One or more updates failed.' if not all_tasks_successful else '')}"
                if all_tasks_successful:
                    logger.info(
                        "Update-all-backends command completed successfully for %s plugin(s).",
                        len(plugins_to_update),
                    )
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=all_tasks_successful,
                    message=final_message,
                    task_registry=manager.dependencies.infrastructure.task_registry,
                    send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
            except asyncio.CancelledError:
                logger.info("Bulk backend update cancelled by user request.")
                await notify_operation_cancelled(
                    "Update of all plugin backends",
                    reply_channel,
                    task_id,
                    manager.dependencies.infrastructure.task_registry,
                    manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
                raise
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Error during update-all-backends command",
                    operation=OPERATION_PLUGIN_FLOW_PROCESS_UPDATE_ALL_BACKENDS_ASYNC,
                )
                await send_unexpected_error_completion_for_plugin_manager(
                    manager,
                    reply_channel,
                    task_id,
                    exception,
                )
    except TaskIDCollisionError as exception:
        await handle_plugin_manager_task_id_collision(manager, exception, reply_channel)

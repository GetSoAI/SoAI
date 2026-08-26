"""SoAI - Model delete and purge workflows [backend/models/actions/delete_workflows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation import create_cancellation_watch_task
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_models_model_commands import ModelDeleteCommand
from core.events.types_plugins import PurgeModelsForPluginCommand
from core.logging.trace import get_logger
from core.models.provider_backing import is_provider_backed_model
from core.plugins.errors import PluginCapabilityError
from core.tasks.api_events import send_task_complete_event, send_task_progress_event
from core.tasks.cancel_watcher import cleanup_cancel_watcher
from core.tasks.cancellation_id import require_command_cancellation_id
from core.tasks.cancellation_token_scope import cancellation_token_scope
from models.actions.dependencies import ModelActionsServiceDependencies
from models.actions.operations import (
    create_delete_task_if_needed,
    create_purge_delete_context,
    execute_model_file_deletion,
)
from models.actions.plugin_stop_waiting import ensure_plugin_stopped_for_delete
from models.catalog_locking import catalog_mutation_lock_scope

__all__ = (
    "process_model_delete_command",
    "process_model_purge_for_plugin_command",
)

LOGGER_NAME = "SoAI.models.actions.delete_workflows"
OPERATION_MODELS_ACTIONS_MODEL_PROCESS_DELETE_COMMAND_ASYNC = (
    "models.actions.model_process_delete_command_async"
)
OPERATION_MODELS_ACTIONS_MODEL_PROCESS_PURGE_FOR_PLUGIN_ASYNC = (
    "models.actions.model_process_purge_for_plugin_async"
)


async def process_model_delete_command(
    deps: ModelActionsServiceDependencies,
    command: ModelDeleteCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    universal_id = command.universal_id
    reply_channel = command.reply_channel
    cancellation_id = require_command_cancellation_id(command)
    shutdown_event = asyncio.Event()
    cancel_watcher: asyncio.Task[None] | None = None
    try:
        extracted_cancellation_id = await create_delete_task_if_needed(
            reply_channel,
            command.context,
            universal_id,
            deps.task_registry,
        )
        if extracted_cancellation_id is not None:
            cancellation_id = extracted_cancellation_id
        initial_info = await deps.database_models.get_model_info(universal_id)
        if not initial_info:
            await send_task_complete_event(
                reply_channel,
                f"Model '{universal_id}' not found.",
                success=False,
                error_code=404,
                registry=deps.task_registry,
            )
            return
        plugin_name_value = initial_info.get("plugin")
        if not isinstance(plugin_name_value, str) or not plugin_name_value:
            await send_task_complete_event(
                reply_channel,
                f"Model '{universal_id}' has no associated plugin.",
                success=False,
                error_code=500,
                registry=deps.task_registry,
            )
            return
        plugin_name = plugin_name_value
        async with catalog_mutation_lock_scope(
            deps.plugin_manager.lifecycle,
            deps.model_record_locks,
            (plugin_name,),
            (universal_id,),
        ):
            authoritative_info = await deps.database_models.get_model_info(universal_id)
            if authoritative_info is None:
                await send_task_complete_event(
                    reply_channel,
                    "Model deletion was superseded because concurrent plugin deletion removed its model record.",
                    success=False,
                    cancelled=True,
                    registry=deps.task_registry,
                )
                return
            authoritative_plugin_value = authoritative_info.get("plugin")
            if authoritative_plugin_value != plugin_name:
                raise StateError(
                    "Model plugin identity changed while acquiring deletion locks.",
                    operation="models.actions.process_model_delete_command",
                    details={
                        "universal_id": universal_id,
                        "expected_plugin_name": plugin_name,
                        "authoritative_plugin_name": authoritative_plugin_value,
                    },
                )
            if is_provider_backed_model(authoritative_info):
                await send_task_complete_event(
                    reply_channel,
                    "Provider-backed models cannot be deleted directly. Remove or disable the external provider to remove its models from SoAI.",
                    success=False,
                    error_code=400,
                    registry=deps.task_registry,
                )
                return
            try:
                await deps.plugin_manager.ensure_plugin_capability(
                    plugin_name,
                    "SUPPORTS_MODEL_DELETION",
                    "Model Deletion",
                )
            except PluginCapabilityError as exception:
                await send_task_complete_event(
                    reply_channel,
                    str(exception),
                    success=False,
                    error_code=400,
                    registry=deps.task_registry,
                )
                return
            if not await ensure_plugin_stopped_for_delete(
                plugin_name,
                reply_channel,
                command.context,
                deps.state_aggregator,
                deps.task_registry,
                deps.event_bus,
                deps.config,
            ):
                return
            await send_task_progress_event(
                reply_channel,
                percent=30,
                message="Plugin stopped. Deleting model files...",
                registry=deps.task_registry,
            )
            if cancellation_id is None:
                raise StateError("cancellation_id must be set for model delete operation")
            plugin_instance = await deps.plugin_manager.require_loaded_plugin(
                plugin_name,
                auto_load=True,
                already_serialized=True,
            )
            try:
                async with cancellation_token_scope(
                    deps.token_collection,
                    deps.cancellation_history,
                    deps.cancellation_event_bus,
                    cancellation_id=cancellation_id,
                    owner="model_delete",
                    metadata={"universal_id": universal_id},
                    logger=logger,
                ) as token:
                    cancel_watcher = create_cancellation_watch_task(
                        token,
                        shutdown_event,
                        name=f"model-delete-cancel-watch-{universal_id}",
                    )
                    success, message = await execute_model_file_deletion(
                        plugin_instance,
                        authoritative_info,
                        reply_channel,
                        shutdown_event,
                        deps.task_registry,
                    )
            finally:
                await uncancel_then_cleanup(
                    deps.plugin_manager.release_discovery_plugin_instance(plugin_name),
                )
            if success:
                await deps.mutation_effects.finalize_model_deletion(universal_id)
                await send_task_complete_event(
                    reply_channel,
                    message or f"Model '{universal_id}' deleted successfully.",
                    registry=deps.task_registry,
                )
                return
            await send_task_complete_event(
                reply_channel,
                message or f"Plugin failed to delete model '{universal_id}'.",
                success=False,
                error_code=500,
                registry=deps.task_registry,
            )
    except asyncio.CancelledError:
        shutdown_event.set()
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Model delete command failed.",
            operation=OPERATION_MODELS_ACTIONS_MODEL_PROCESS_DELETE_COMMAND_ASYNC,
            details={"universal_id": universal_id},
            level="warning",
        )
        await send_task_complete_event(
            reply_channel,
            "Model deletion failed.",
            success=False,
            error_code=500,
            registry=deps.task_registry,
        )
    finally:
        await cleanup_cancel_watcher(
            cancel_watcher,
            operation="models.actions.cleanup_cancel_watcher",
            logger=logger,
        )


async def process_model_purge_for_plugin_command(
    deps: ModelActionsServiceDependencies,
    command: PurgeModelsForPluginCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        models_by_plugin = await deps.database_models.get_all_models_by_plugin()
        for info in models_by_plugin.get(command.plugin_name, {}).values():
            universal_id_value = info.get("universal_id")
            if not isinstance(universal_id_value, str) or not universal_id_value:
                continue
            universal_id = universal_id_value
            delete_context, reply_queue = await create_purge_delete_context(
                command.context,
                command.plugin_name,
                universal_id,
                deps.task_registry,
            )
            await process_model_delete_command(
                deps,
                ModelDeleteCommand(
                    reply_channel=reply_queue,
                    universal_id=universal_id,
                    context=delete_context,
                ),
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Model purge command failed.",
            operation=OPERATION_MODELS_ACTIONS_MODEL_PROCESS_PURGE_FOR_PLUGIN_ASYNC,
            details={"plugin_name": command.plugin_name},
            level="warning",
        )

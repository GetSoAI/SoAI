"""SoAI - Plugin clone command handler [backend/plugins/clone/command_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError, StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_plugins import ClonePluginCommand
from core.logging.trace import get_logger
from core.tasks.errors import TaskIDCollisionError
from core.validation.strict_numbers import require_positive_int_strict
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.actions.progress import (
    create_task_progress_sender,
    notify_operation_cancelled,
    send_completion_with_task,
)
from plugins.clone.clone_execution import cleanup_failed_clone, execute_clone
from plugins.clone.clone_replay import (
    reconcile_committed_clone_after_cancellation,
    reconcile_replayed_clone,
)
from plugins.context_ids import (
    resolve_task_id_from_context,
    resolve_user_id_from_context,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.task_collisions import handle_task_id_collision_error

__all__ = ("process_clone_command_async",)

LOGGER_NAME = "SoAI.plugins.clone.command_handler"
OPERATION = "plugin_clone.process_clone_command_async"


async def process_clone_command_async(
    plugin_manager: PluginManagerRuntimeProtocol,
    command: ClonePluginCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    plugin_name = command.plugin_name
    reply_channel = command.reply_channel
    context = command.context
    clone_models = command.clone_models
    field_overrides = command.field_overrides
    plan = None
    user_id = resolve_user_id_from_context(context)
    task_id_value = resolve_task_id_from_context(context)
    try:
        if task_id_value is None:
            raise StateError("Clone execution requires a durable accepted task identity.")
        fencing_token = require_positive_int_strict(
            context.mutation_fencing_token if context is not None else None,
            error_message="Clone execution requires a durable mutation fencing token.",
        )
        replayed_transaction = await reconcile_replayed_clone(
            plugin_manager,
            command,
            task_id_value,
            execute_admitted=True,
        )
        if replayed_transaction is None:
            raise StateError("Clone execution requires an atomic admission journal.")
        if replayed_transaction.phase != "admitted":
            if not (
                replayed_transaction.committed
                or replayed_transaction.phase in {"committed", "recovery_required", "rolled_back"}
            ):
                await cleanup_failed_clone(
                    plugin_manager,
                    task_id=task_id_value,
                    fencing_token=fencing_token,
                )
                await reconcile_replayed_clone(
                    plugin_manager,
                    command,
                    task_id_value,
                )
            return
        async with plugin_manager.dependencies.infrastructure.lifecycle.lifecycle_scope(
            service_name="Plugin manager",
            task_type="clone_plugin",
            plugin_name=plugin_name,
            metadata={
                "operation": "clone_plugin",
                "display_name": await plugin_manager.get_plugin_display_name(plugin_name),
                "clone_models": clone_models,
            },
            acquire_plugin_lock=False,
            user_id=user_id,
            task_id=task_id_value,
            context=context,
        ) as (_, task_id):
            if task_id is None:
                raise StateError("Clone lifecycle scope did not yield a task_id.")
            progress_callback = create_task_progress_sender(
                reply_channel,
                task_id,
                plugin_manager.dependencies.infrastructure.task_registry,
                plugin_manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
            )
            try:
                await progress_callback(1, "Validating source plugin...")
                if not await validate_action_for_state_async(
                    plugin_manager,
                    plugin_name,
                    "clone",
                    reply_channel,
                    task_id,
                    mutation_fencing_token=fencing_token,
                ):
                    await cleanup_failed_clone(
                        plugin_manager,
                        task_id=task_id,
                        fencing_token=fencing_token,
                    )
                    return
                plan, message = await execute_clone(
                    plugin_manager,
                    source_plugin_name=plugin_name,
                    reserved_target_name=replayed_transaction.target_plugin_name,
                    clone_models=clone_models,
                    field_overrides=field_overrides,
                    reply_channel=reply_channel,
                    task_id=task_id,
                    context=context,
                    progress_callback=progress_callback,
                    fencing_token=fencing_token,
                )
                logger.info(message)
            except asyncio.CancelledError:
                if await uncancel_and_wait(
                    reconcile_committed_clone_after_cancellation(
                        plugin_manager,
                        command,
                        task_id,
                    )
                ):
                    raise
                logger.info(
                    "Clone operation for plugin '%s' cancelled by user request.",
                    plan.source_display_name if plan is not None else plugin_name,
                )
                await cleanup_failed_clone(
                    plugin_manager,
                    task_id=task_id,
                    fencing_token=fencing_token,
                )
                await notify_operation_cancelled(
                    "Plugin clone",
                    reply_channel,
                    task_id,
                    plugin_manager.dependencies.infrastructure.task_registry,
                    send_task_complete_event_callable=plugin_manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                    mutation_fencing_token=fencing_token,
                )
                raise
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                durable_transaction = (
                    await plugin_manager.dependencies.databases.plugins.clone_transactions.get(
                        task_id
                    )
                )
                if durable_transaction is not None and (
                    durable_transaction.committed or durable_transaction.phase == "committed"
                ):
                    log_handled_exception(
                        logger,
                        exception,
                        message="Clone completion delivery failed after durable commit.",
                        operation=OPERATION,
                        details={"plugin": plugin_name, "task_id": task_id},
                        level="warning",
                    )
                    return
                details = {
                    "plugin": (
                        plan.source_display_name or plugin_name if plan is not None else plugin_name
                    ),
                }
                if isinstance(exception, InsufficientDiskSpaceError):
                    log_handled_exception(
                        logger,
                        exception,
                        message=str(exception.message),
                        operation=OPERATION,
                        details={**details, **dict(exception.details or {})},
                        level="warning",
                    )
                else:
                    log_exception(
                        logger,
                        exception,
                        message="Error during clone",
                        operation=OPERATION,
                        details=details,
                    )
                await cleanup_failed_clone(
                    plugin_manager,
                    task_id=task_id,
                    fencing_token=fencing_token,
                )
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=False,
                    message=(
                        str(exception.message)
                        if isinstance(exception, InsufficientDiskSpaceError)
                        else f"Failed to clone plugin: {exception}"
                    ),
                    error_code=(
                        exception.http_status
                        if isinstance(exception, InsufficientDiskSpaceError)
                        else None
                    ),
                    error_message=(
                        str(exception.message)
                        if isinstance(exception, InsufficientDiskSpaceError)
                        else None
                    ),
                    mutation_fencing_token=fencing_token,
                    task_registry=plugin_manager.dependencies.infrastructure.task_registry,
                    send_task_complete_event_callable=plugin_manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
    except TaskIDCollisionError as exception:
        await handle_task_id_collision_error(
            exception,
            reply_channel,
            plugin_manager.dependencies.infrastructure.task_helpers.send_error_event,
        )

"""SoAI - Plugin backend lifecycle task execution and management [backend/plugins/actions/backend_lifecycle_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import cancellation_cleanup
from core.errors.exceptions import SoAIError, StateError
from core.events.completion_waiting import await_publication_receipt
from core.events.types_plugins import (
    InstallPluginBackendCommand,
    RemovePluginBackendCommand,
    UpdatePluginBackendCommand,
)
from core.logging.trace import get_logger
from core.runtime.network_policy import is_offline_mode_enabled
from core.runtime.request_context import RequestContext
from core.tasks.protocols import TaskRegistryProtocol
from plugins.actions.backend_lifecycle_backend_actions import (
    execute_backend_action,
    finalize_successful_backend_action,
    finalize_successful_model_removal,
)
from plugins.actions.backend_lifecycle_error_handling import (
    LifecycleErrorContext,
    handle_lifecycle_cancelled,
    handle_lifecycle_failure,
)
from plugins.actions.backend_lifecycle_output_progress import (
    LifecycleOutputProgressReporter,
)
from plugins.actions.backend_lifecycle_state import capture_original_plugin_state_noncritical
from plugins.actions.backend_lifecycle_task_identity import resolve_lifecycle_task_id
from plugins.actions.backend_update_checkpoints import (
    advance_backend_update,
    contain_backend_update,
    require_backend_update_identity,
)
from plugins.actions.backend_update_verification import (
    complete_backend_update_verification,
    validate_updated_backend,
)
from plugins.actions.progress import (
    send_completion_with_task,
    send_progress_with_task,
)
from plugins.manager.capability_support import supports_plugin_capability_from_instance
from plugins.manager.policy import LifecycleActionPolicy
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.events.types_base import Event

__all__ = ()

LOGGER_NAME = "SoAI.plugins.actions.backend_lifecycle_execution"


async def _require_lifecycle_action_allowed_or_respond(
    *,
    manager: PluginManagerRuntimeProtocol,
    action: str,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    task_registry: TaskRegistryProtocol,
    mutation_fencing_token: int | None,
) -> bool:
    if action not in {"install_backend", "update_backend"}:
        return True
    if not is_offline_mode_enabled(manager.dependencies.infrastructure.runtime_flags):
        return True
    if task_id is None:
        return False
    await send_completion_with_task(
        reply_channel,
        task_id,
        success=False,
        message="Backend install/update is disabled because SYSTEM.RUNTIME.STAY_OFFLINE is enabled.",
        mutation_fencing_token=mutation_fencing_token,
        task_registry=task_registry,
        send_task_complete_event_callable=(
            manager.dependencies.infrastructure.task_helpers.send_task_complete_event
        ),
    )
    return False


async def _send_lifecycle_task_started(
    *,
    manager: PluginManagerRuntimeProtocol,
    output_progress: LifecycleOutputProgressReporter,
    action: str,
    display_name: str,
    plugin_name: str,
    context: RequestContext | None,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    action_config: LifecycleActionPolicy,
) -> None:
    if task_id is None:
        return
    task_registry = manager.dependencies.infrastructure.task_registry
    await send_progress_with_task(
        reply_channel,
        task_id,
        output_progress.map_progress(0),
        f"Initializing task '{action}' for '{display_name}'...",
        task_registry,
        manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
    )
    receipt = await manager.transition_plugin_manager_state(
        plugin_name,
        action_config.transient,
        f"Starting task '{action}'.",
        context,
    )
    await await_publication_receipt(receipt)


async def execute_lifecycle_task(
    manager: PluginManagerRuntimeProtocol,
    command: InstallPluginBackendCommand | UpdatePluginBackendCommand | RemovePluginBackendCommand,
    action: str,
    send_completion_event: bool = True,
    is_part_of_delete: bool = False,
    task_id: str | None = None,
    progress_mapper: Callable[[int], int] | None = None,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    plugin_name, reply_channel, context = (
        command.plugin_name,
        command.reply_channel,
        command.context,
    )
    trace_id = context.trace_id if context else "no-context"
    mutation_fencing_token = context.mutation_fencing_token if context is not None else None
    action_config = manager.policy.lifecycle_action_config[action]
    display_name = await manager.get_plugin_display_name(plugin_name)
    original_state = await capture_original_plugin_state_noncritical(
        manager=manager,
        plugin_name=plugin_name,
        trace_id=trace_id,
        action=action,
        display_name=display_name,
        logger=logger,
    )
    task_registry = manager.dependencies.infrastructure.task_registry
    task_id = resolve_lifecycle_task_id(command, task_registry, task_id)
    output_progress = LifecycleOutputProgressReporter(
        logger=logger,
        trace_id=trace_id,
        action=action,
        display_name=display_name,
        reply_channel=reply_channel,
        task_id=task_id,
        task_registry=task_registry,
        send_task_progress_event=manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
        progress_mapper=progress_mapper,
    )
    if not await _require_lifecycle_action_allowed_or_respond(
        manager=manager,
        action=action,
        reply_channel=reply_channel,
        task_id=task_id,
        task_registry=task_registry,
        mutation_fencing_token=mutation_fencing_token,
    ):
        return False
    plugin_instance = None
    failure: Exception | None = None
    error_context: LifecycleErrorContext = {
        "action": action,
        "display_name": display_name,
        "plugin_name": plugin_name,
        "context": context,
        "trace_id": trace_id,
        "original_state": original_state,
        "is_part_of_delete": is_part_of_delete,
        "send_completion_event": send_completion_event,
        "reply_channel": reply_channel,
        "task_id": task_id,
        "mutation_fencing_token": mutation_fencing_token,
    }
    try:
        if not isinstance(command, UpdatePluginBackendCommand):
            await manager.dependencies.databases.plugins.invalidate_backend_update(plugin_name)
        plugin_instance = await manager.require_loaded_plugin(plugin_name, auto_load=True)
        if action in {
            "install_backend",
            "update_backend",
        } and supports_plugin_capability_from_instance(
            plugin_instance,
            "SUPPORTS_CONFIGURATION",
        ):
            await plugin_instance.refresh_runtime_configuration()
        if not is_part_of_delete:
            await _send_lifecycle_task_started(
                manager=manager,
                output_progress=output_progress,
                action=action,
                display_name=display_name,
                plugin_name=plugin_name,
                context=context,
                reply_channel=reply_channel,
                task_id=task_id,
                action_config=action_config,
            )
        recovered_callback = False
        if isinstance(command, UpdatePluginBackendCommand):
            await require_backend_update_identity(manager, command)
            claim = command.mutation_claim
            if claim is not None:
                recovered_callback = claim.execution_phase in {"callback_succeeded", "verified"}
                if not recovered_callback and (
                    claim.execution_phase != "execution_started" or claim.attempt_count != 1
                ):
                    raise StateError(
                        "Interrupted backend update requires repair; mutation was not repeated."
                    )
        success = recovered_callback or await execute_backend_action(
            action=action,
            command=command,
            plugin_instance=plugin_instance,
            output_callback=output_progress.output_callback,
        )
        if not success:
            raise StateError(
                f"Action '{action}' failed during execution, plugin returned unsuccessful.",
            )
        if isinstance(command, UpdatePluginBackendCommand):
            if not recovered_callback:
                await advance_backend_update(manager, command, "callback_succeeded")
            await validate_updated_backend(manager, command, plugin_instance)
        if isinstance(command, RemovePluginBackendCommand):
            await finalize_successful_model_removal(manager, command)
        if not is_part_of_delete:
            await finalize_successful_backend_action(
                manager=manager,
                plugin_name=plugin_name,
                action=action,
                display_name=display_name,
                context=context,
                action_config=action_config,
                plugin_instance=plugin_instance,
                logger=logger,
            )
        if isinstance(command, RemovePluginBackendCommand):
            await manager.dependencies.databases.plugins.delete_backend_update(plugin_name)
        if not isinstance(command, UpdatePluginBackendCommand):
            manager.state.catalog.backend_update_publication_pending = True
            manager.state.catalog.backend_update_wake.set()
            logger.info("Task '%s' for '%s' completed successfully.", action, display_name)
            if send_completion_event:
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=True,
                    message=f"Task '{action}' for '{display_name}' finished.",
                    mutation_fencing_token=mutation_fencing_token,
                    task_registry=manager.dependencies.infrastructure.task_registry,
                    send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
            return True
    except asyncio.CancelledError:
        try:
            if isinstance(command, UpdatePluginBackendCommand):
                await cancellation_cleanup(contain_backend_update(manager, command))
            await cancellation_cleanup(
                handle_lifecycle_cancelled(
                    manager,
                    logger,
                    plugin_instance=plugin_instance,
                    **error_context,
                )
            )
        except SoAIError as exception:
            failure = exception
        else:
            raise
    except (SoAIError, TimeoutError) as exception:
        failure = exception
    finally:
        await output_progress.flush()
    if failure is not None:
        if isinstance(command, UpdatePluginBackendCommand):
            await contain_backend_update(manager, command)
        should_return_false = await handle_lifecycle_failure(
            manager,
            logger,
            exception=failure,
            plugin_instance=plugin_instance,
            **error_context,
        )
        if should_return_false:
            return False
        raise failure
    if not isinstance(command, UpdatePluginBackendCommand):
        raise StateError("Backend lifecycle ended without an operation outcome.")
    return await complete_backend_update_verification(
        manager,
        command,
        task_id=task_id,
        send_completion_event=send_completion_event,
    )

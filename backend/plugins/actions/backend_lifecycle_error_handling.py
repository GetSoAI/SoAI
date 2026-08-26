"""SoAI - Plugin backend lifecycle error handling [backend/plugins/actions/backend_lifecycle_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import await_publication_receipt
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_STOPPED,
)
from plugins.actions.backend_lifecycle_state import require_runtime_state
from plugins.actions.backend_lifecycle_validation import cleanup_partial_installation
from plugins.actions.progress import (
    notify_operation_cancelled,
    send_completion_with_task,
)
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext

__all__ = (
    "handle_lifecycle_cancelled",
    "handle_lifecycle_failure",
)

OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK = "plugin_flow.execute_lifecycle_task"
OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_CLEANUP_PARTIAL_INSTALLATION = (
    "plugin_flow.execute_lifecycle_task.cleanup_partial_installation"
)


async def handle_lifecycle_cancelled(
    manager: PluginManagerRuntimeProtocol,
    logger: LoggerProtocol,
    *,
    action: str,
    display_name: str,
    plugin_name: str,
    context: RequestContext | None,
    trace_id: str,
    original_state: str | None,
    plugin_instance: PluginInstanceProtocol | None,
    is_part_of_delete: bool,
    send_completion_event: bool,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    mutation_fencing_token: int | None,
) -> None:
    logger.info("Lifecycle task '%s' for '%s' was cancelled by user request.", action, display_name)
    if not is_part_of_delete:
        try:
            await cleanup_partial_installation(manager, plugin_instance, plugin_name, action)
        except RECOVERABLE_EXCEPTIONS as cleanup_error:
            log_exception(
                logger,
                cleanup_error,
                message="Error cleaning up partial installation after cancellation.",
                operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK_CLEANUP_PARTIAL_INSTALLATION,
                details={"trace_id": trace_id, "action": action, "plugin": display_name},
                level="warning",
            )
        target_state = (
            PLUGIN_STATE_BACKEND_NOT_INSTALLED
            if action == "install_backend"
            else (
                require_runtime_state(
                    original_state,
                    operation="plugin_flow.execute_lifecycle_task.cancelled",
                    plugin_name=plugin_name,
                    trace_id=trace_id,
                )
                if original_state is not None
                else PLUGIN_STATE_STOPPED
            )
        )
        receipt = await manager.transition_plugin_manager_state(
            plugin_name,
            target_state,
            f"Task '{action}' cancelled by user. Rolled back to stable state.",
            context,
        )
        await await_publication_receipt(receipt)
    if send_completion_event:
        await notify_operation_cancelled(
            f"Task '{action}' for '{display_name}'",
            reply_channel,
            task_id,
            manager.dependencies.infrastructure.task_registry,
            manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
            mutation_fencing_token=mutation_fencing_token,
        )


async def handle_lifecycle_failure(
    manager: PluginManagerRuntimeProtocol,
    logger: LoggerProtocol,
    *,
    action: str,
    display_name: str,
    plugin_name: str,
    context: RequestContext | None,
    trace_id: str,
    is_part_of_delete: bool,
    send_completion_event: bool,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    exception: Exception,
    mutation_fencing_token: int | None,
) -> bool:
    action_config = manager.policy.lifecycle_action_config[action]
    log_exception(
        logger,
        exception,
        message=f"Plugin lifecycle task '{action}' for '{display_name}' failed",
        operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK,
        details={"trace_id": trace_id, "action": action, "plugin": display_name},
    )
    if send_completion_event:
        await send_completion_with_task(
            reply_channel,
            task_id,
            success=False,
            message=f"Error: {exception}",
            mutation_fencing_token=mutation_fencing_token,
            task_registry=manager.dependencies.infrastructure.task_registry,
            send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
        )
    if is_part_of_delete:
        return False
    logger.warning(
        "Lifecycle task '%s' for '%s' failed or timed out. Reverting to a stable error state to prevent lock-up.",
        action,
        display_name,
    )
    receipt = await manager.transition_plugin_manager_state(
        plugin_name,
        action_config.error,
        f"Task for '{action}' failed.",
        context,
    )
    await await_publication_receipt(receipt)
    return True

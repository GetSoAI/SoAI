"""SoAI - Plugin backend lifecycle error handling [backend/plugins/actions/backend_lifecycle_error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING, TypedDict

from core.errors.backend_lifecycle import IpcCancellationCleanupError, backend_prerequisite_message
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError
from core.errors.public_projection import (
    project_public_exception,
    project_specific_public_exception,
)
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.completion_waiting import await_publication_receipt
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.state_names import (
    ORCH_STATE_QUARANTINED,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_STOPPED,
)
from plugins.actions.backend_lifecycle_state import (
    require_runtime_state,
    resolve_retained_backend_state,
)
from plugins.actions.backend_lifecycle_validation import cleanup_partial_installation
from plugins.actions.progress import (
    notify_operation_cancelled,
    send_completion_with_task,
)
from plugins.manager.backend_update_containment import contain_backend_update_worker
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext

__all__ = (
    "LifecycleErrorContext",
    "handle_lifecycle_cancelled",
    "handle_lifecycle_failure",
)

OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK = "plugin_flow.execute_lifecycle_task"


class LifecycleErrorContext(TypedDict):
    action: str
    display_name: str
    plugin_name: str
    context: RequestContext | None
    trace_id: str
    original_state: str | None
    is_part_of_delete: bool
    send_completion_event: bool
    reply_channel: asyncio.Queue[Event] | None
    task_id: str | None
    mutation_fencing_token: int | None


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
        except HANDLED_RUNTIME_EXCEPTIONS as cleanup_error:
            raise IpcCancellationCleanupError(
                "Backend cancellation cleanup failed.", cause=cleanup_error
            ) from cleanup_error
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
        if action in {"install_backend", "update_backend"}:
            target_state = await resolve_retained_backend_state(
                plugin_instance,
                fallback_state=manager.policy.lifecycle_action_config[action].error,
                absent_state=PLUGIN_STATE_BACKEND_NOT_INSTALLED,
                logger=logger,
            )
        receipt = await manager.transition_plugin_manager_state(
            plugin_name,
            target_state,
            f"Task '{action}' cancelled. Backend state reconciled.",
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
    plugin_instance: PluginInstanceProtocol | None,
    original_state: str | None = None,
) -> bool:
    action_config = manager.policy.lifecycle_action_config[action]
    error = coerce_to_soai_error(exception, trace_id=trace_id)
    prerequisite_rejected = backend_prerequisite_message(error.code) is not None
    containment_failed = False
    if error.code == IpcCancellationCleanupError.code:
        try:
            await contain_backend_update_worker(manager, plugin_name)
        except HANDLED_RUNTIME_EXCEPTIONS as containment_error:
            containment_failed = True
            error.add_note(
                f"Backend containment remains unverified: {type(containment_error).__name__}"
            )
            if manager.orchestrator_lifecycle is not None:
                await manager.orchestrator_lifecycle.circuit_breakers.trip_circuit_breaker(
                    plugin_name
                )
    log_exception(
        logger,
        exception,
        message=f"Plugin lifecycle task '{action}' for '{display_name}' failed",
        operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK,
        details={"trace_id": trace_id, "action": action, "plugin": display_name},
        level=(
            "warning"
            if prerequisite_rejected
            or error.code
            in (
                InsufficientDiskSpaceError.code,
                "backend_runtime_incompatible",
                "managed_compiler_unavailable",
                "runtime_verification_failed",
            )
            else "error"
        ),
    )
    if send_completion_event:
        public_error = project_specific_public_exception(exception, trace_id=trace_id)
        if public_error is None:
            public_error = project_public_exception(exception, trace_id=trace_id)
            if action in {"install_backend", "update_backend"}:
                public_error = replace(
                    public_error,
                    message="Backend installation or update failed. Check the selected variant's runtime requirements and server diagnostics, then retry.",
                )
        await send_completion_with_task(
            reply_channel,
            task_id,
            success=False,
            message=public_error.message,
            error_message=public_error.message,
            public_error=public_error,
            error_code=error.http_status,
            error_type=str(public_error.code),
            mutation_fencing_token=mutation_fencing_token,
            task_registry=manager.dependencies.infrastructure.task_registry,
            send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
        )
    if is_part_of_delete:
        return False
    target_state = action_config.error
    if containment_failed:
        target_state = ORCH_STATE_QUARANTINED
    elif prerequisite_rejected:
        target_state = require_runtime_state(
            original_state or PLUGIN_STATE_BACKEND_NOT_INSTALLED,
            operation=OPERATION_PLUGIN_FLOW_EXECUTE_LIFECYCLE_TASK,
            plugin_name=plugin_name,
            trace_id=trace_id,
        )
    elif action in {"install_backend", "update_backend"}:
        target_state = await resolve_retained_backend_state(
            plugin_instance,
            fallback_state=target_state,
            absent_state=target_state,
            logger=logger,
        )
    logger.info(
        "Lifecycle task '%s' for '%s' failed; publishing verified runtime state %s.",
        action,
        display_name,
        target_state,
    )
    receipt = await manager.transition_plugin_manager_state(
        plugin_name,
        target_state,
        f"Task for '{action}' failed.",
        context,
    )
    await await_publication_receipt(receipt)
    return True

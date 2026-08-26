"""SoAI - Shared WebSocket plugin admin action support [backend/features/api/routes/system/events/websocket_admin_plugin_action_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event, ReplyableCommand
from core.logging.trace import get_logger
from core.plugins.errors import PluginCapabilityError
from features.api.routes.system.events.websocket_admin_command_dispatch import (
    dispatch_replyable_command_accepted,
)
from features.api.routes.system.events.websocket_errors import (
    enqueue_connection_server_error,
    enqueue_connection_soai_error,
    enqueue_websocket_error,
)
from features.api.routes.system.events.websocket_run_payloads import resolve_run_id
from features.api.runtime.plugin_compatibility import ensure_plugin_compatible_or_raise

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json_value import JSONValue
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "PluginAdminDispatchContext",
    "dispatch_plugin_admin_command_accepted",
    "dispatch_plugin_admin_command_accepted_for_context",
    "enqueue_plugin_admin_invalid_request",
    "ensure_plugin_admin_action_allowed",
    "resolve_run_id",
)

LOGGER_NAME = "SoAI.features.api.websocket_admin_plugin_action_support"
OPERATION = "api_system.websocket.system_events.plugin_admin_command_dispatch"


async def enqueue_plugin_admin_invalid_request(
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    run_id: str | None,
    message: str,
    code: str,
) -> None:
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        "invalid_request",
        message,
        code=code,
        run_id=run_id,
    )


async def _handle_plugin_admin_soai_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
    trace_id: str | None,
    exception: SoAIError,
    run_id: str | None,
) -> bool:
    await enqueue_connection_soai_error(
        enqueue_warning_tracker=enqueue_warning_tracker,
        connection=connection,
        trace_id=trace_id,
        exception=exception,
        run_id=run_id,
    )
    return False


async def ensure_plugin_admin_action_allowed(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    run_id: str | None,
    plugin_name: str,
    capability_name: str,
    capability_label: str,
    action_label: str,
    action_key: str,
) -> bool:
    plugin_manager_instance = api_context.dependencies.plugin_manager
    try:
        await ensure_plugin_compatible_or_raise(
            request,
            plugin_manager_instance,
            plugin_name,
        )
        await plugin_manager_instance.ensure_plugin_capability(
            plugin_name,
            capability_name,
            capability_label,
        )
        await plugin_manager_instance.ensure_system_capabilities(
            plugin_name,
            action_label,
            action_key=action_key,
        )
    except PluginCapabilityError as exception:
        await enqueue_plugin_admin_invalid_request(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            run_id=run_id,
            message=str(exception),
            code="action_not_supported",
        )
        return False
    except SoAIError as exception:
        return await _handle_plugin_admin_soai_error(
            enqueue_warning_tracker,
            connection,
            trace_id,
            exception,
            run_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Plugin admin capability validation failed.",
            operation=OPERATION,
            trace_id=trace_id,
            details={"plugin_name": plugin_name},
            level="warning",
        )
        await enqueue_connection_server_error(
            enqueue_warning_tracker=enqueue_warning_tracker,
            connection=connection,
            trace_id=trace_id,
            run_id=run_id,
        )
        return False
    return True


async def dispatch_plugin_admin_command_accepted(
    request: RequestProtocol,
    *,
    api_context: ApiContext,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    run_id: str | None,
    plugin_name: str,
    capability_name: str,
    capability_label: str,
    action_label: str,
    action_key: str,
    command_type: type[Event],
    command_factory: Callable[..., ReplyableCommand],
    audit_action: str,
    audit_target: str,
    audit_details: dict[str, JSONValue],
    command_fields: dict[str, JSONValue],
    task_id: str | None,
    requires_mutation_id: bool,
) -> str | None:
    action_allowed = await ensure_plugin_admin_action_allowed(
        request=request,
        api_context=api_context,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        run_id=run_id,
        plugin_name=plugin_name,
        capability_name=capability_name,
        capability_label=capability_label,
        action_label=action_label,
        action_key=action_key,
    )
    if not action_allowed:
        return None
    return await dispatch_replyable_command_accepted(
        request,
        api_context=api_context,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        command_type=command_type,
        command_factory=command_factory,
        audit_action=audit_action,
        audit_target=audit_target,
        audit_details=audit_details,
        task_id=task_id,
        requires_mutation_id=requires_mutation_id,
        run_id=run_id,
        command_fields=command_fields,
    )


@dataclass(frozen=True, slots=True)
class PluginAdminDispatchContext:
    request: RequestProtocol
    api_context: ApiContext
    connection: WebsocketConnection
    enqueue_warning_tracker: EnqueueWarningTracker
    trace_id: str | None
    run_id: str | None
    plugin_name: str
    task_id: str | None = None
    requires_mutation_id: bool = False


async def dispatch_plugin_admin_command_accepted_for_context(
    context: PluginAdminDispatchContext,
    *,
    capability_name: str,
    capability_label: str,
    action_label: str,
    action_key: str,
    command_type: type[Event],
    command_factory: Callable[..., ReplyableCommand],
    audit_action: str,
    audit_target: str,
    audit_details: dict[str, JSONValue],
    command_fields: dict[str, JSONValue],
) -> str | None:
    return await dispatch_plugin_admin_command_accepted(
        context.request,
        api_context=context.api_context,
        connection=context.connection,
        enqueue_warning_tracker=context.enqueue_warning_tracker,
        trace_id=context.trace_id,
        run_id=context.run_id,
        plugin_name=context.plugin_name,
        capability_name=capability_name,
        capability_label=capability_label,
        action_label=action_label,
        action_key=action_key,
        command_type=command_type,
        command_factory=command_factory,
        audit_action=audit_action,
        audit_target=audit_target,
        audit_details=audit_details,
        command_fields=command_fields,
        task_id=context.task_id,
        requires_mutation_id=context.requires_mutation_id,
    )

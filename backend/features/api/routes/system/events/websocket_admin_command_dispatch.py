"""SoAI - WebSocket admin command dispatch helpers [backend/features/api/routes/system/events/websocket_admin_command_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.database.mutation_requests import MutationAdmissionDraft
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event, ReplyableCommand
from core.logging.trace import get_logger
from core.mutations.identifiers import require_mutation_request_id
from core.runtime.ownership import resolve_http_owner_id
from core.runtime.request_source_resolution import resolve_request_source_for_request
from core.system_api.websocket_payloads import build_websocket_event_payload
from core.tasks.creation import create_streaming_task
from core.tasks.enums import TaskStatus
from core.tasks.errors import TaskIDCollisionError
from core.tasks.identifiers import validate_optional_task_id
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from core.users.user_id import coerce_user_id
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import (
    enqueue_connection_server_error,
    enqueue_connection_soai_error,
    enqueue_websocket_error,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.mutation_dispatch_notification import (
    notify_mutation_dispatch_requested,
)
from features.api.runtime.plugin_mutation_admission import (
    build_backend_mutation_admission,
    resolve_backend_mutation_operation,
)
from features.api.runtime.task_metadata import build_command_task_metadata

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONValue
    from features.api.runtime.context import ApiContext
    from features.api.runtime.plugin_mutation_admission import BackendMutationType
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("dispatch_replyable_command_accepted",)

LOGGER_NAME = "SoAI.features.api.websocket_admin_command_dispatch"
OPERATION = "api_system.websocket.system_events.admin_command_dispatch"


def _build_mutation_admission(
    command_type: type[Event],
    request_id: str | None,
    command_fields: dict[str, JSONValue],
) -> MutationAdmissionDraft | None:
    if request_id is None:
        return None
    operation_type: BackendMutationType = resolve_backend_mutation_operation(command_type)
    plugin_name = command_fields.get("plugin_name")
    if not isinstance(plugin_name, str):
        raise ValidationError("Unsupported durable WebSocket mutation command.")
    return build_backend_mutation_admission(
        request_id=request_id,
        plugin_name=plugin_name,
        operation_type=operation_type,
        command_fields=command_fields,
    )


async def dispatch_replyable_command_accepted(
    request: RequestProtocol,
    *,
    api_context: ApiContext,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    command_type: type[Event],
    command_factory: Callable[..., ReplyableCommand],
    audit_action: str,
    audit_target: str,
    audit_details: dict[str, JSONValue],
    task_id: str | None,
    requires_mutation_id: bool,
    run_id: str | None,
    command_fields: dict[str, JSONValue],
) -> str | None:
    context = request.state.context
    validated_task_id: str | None
    try:
        if requires_mutation_id:
            if task_id is None:
                raise ValidationError("task_id is required for durable mutations.")
            validated_task_id = require_mutation_request_id(task_id)
        else:
            validated_task_id = validate_optional_task_id(task_id, field_name="task_id")
    except ValidationError as exception:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "invalid_request",
            exception.message,
            code=str(exception.code),
            run_id=run_id,
        )
        return None
    if validated_task_id is not None:
        context.task_id = validated_task_id
    log_audit_event(request, audit_action, audit_target, audit_details)
    task_metadata = build_command_task_metadata(
        request,
        command_type,
        audit_action,
        audit_target,
        audit_details,
        command_fields,
    )
    task_type = api_context.dependencies.task_type_routing_service.get_task_type_for_command(
        command_type,
    )
    is_orchestrated_inference = is_orchestrated_inference_task_type(task_type)
    initial_status = TaskStatus.QUEUED if is_orchestrated_inference else TaskStatus.WORKING
    progress_total = None if is_orchestrated_inference else 100
    owner_id = resolve_http_owner_id(context)
    delivery_mode: str | None = "async" if is_orchestrated_inference else None
    request_source = (
        resolve_request_source_for_request(request) if is_orchestrated_inference else None
    )
    mutation_admission = (
        _build_mutation_admission(command_type, validated_task_id, command_fields)
        if requires_mutation_id
        else None
    )
    try:
        task, reply_queue = await create_streaming_task(
            api_context.dependencies.task_registry,
            user_id=coerce_user_id(context.user_id),
            owner_id=owner_id,
            owner_type="http_request",
            task_id=validated_task_id,
            task_type=task_type,
            cancellation_id=context.cancellation_id,
            initial_status=initial_status,
            progress_total=progress_total,
            metadata=task_metadata,
            request_source=request_source,
            delivery_mode=delivery_mode,
            mutation_admission=mutation_admission,
        )
    except TaskIDCollisionError as exception:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            "conflict",
            (
                f"Task with ID '{exception.task_id}' already exists "
                f"(status: {exception.existing_status})."
            ),
            code="task_id_collision",
            run_id=run_id,
        )
        return None
    except SoAIError as exception:
        await enqueue_connection_soai_error(
            enqueue_warning_tracker,
            connection,
            trace_id,
            exception,
            run_id=run_id,
        )
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Unhandled error during WebSocket command dispatch",
            operation=OPERATION,
            trace_id=trace_id,
            level="warning",
        )
        await enqueue_connection_server_error(
            enqueue_warning_tracker,
            connection,
            trace_id,
            run_id=run_id,
        )
        return None
    context.task_id = task.task_id
    if mutation_admission is not None and task.mutation_admission_outcome == "accepted":
        await notify_mutation_dispatch_requested(api_context.dependencies.event_bus)
    if mutation_admission is None:
        cmd = command_factory(reply_channel=reply_queue, context=context, **command_fields)
        try:
            await api_context.dependencies.event_bus.publish(cmd)
        except SoAIError as exception:
            await enqueue_connection_soai_error(
                enqueue_warning_tracker,
                connection,
                trace_id,
                exception,
                task_id=task.task_id,
                run_id=run_id,
            )
            return None
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="Unhandled error publishing WebSocket command",
                operation=OPERATION,
                trace_id=trace_id,
                details={"task_id": task.task_id},
                level="warning",
            )
            await enqueue_connection_server_error(
                enqueue_warning_tracker,
                connection,
                trace_id,
                task_id=task.task_id,
                run_id=run_id,
            )
            return None
    accepted_payload = build_websocket_event_payload(
        WebSocketEventTypes.COMMAND_ACCEPTED,
        {
            "task_id": task.task_id,
            "command": command_type.__name__,
            "audit_action": audit_action,
        },
    )
    if run_id:
        accepted_payload["run_id"] = run_id
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        accepted_payload,
        "WebSocket command accepted",
    )
    return task.task_id

"""SoAI - WebSocket chat stream cancellation [backend/features/api/routes/system/events/chat_stream/cancel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import Task
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_bool
from features.api.routes.system.events.chat_stream.command_errors import (
    enqueue_chat_stream_command_error,
)
from features.api.routes.system.events.chat_stream.command_payload_parsing import (
    connection_has_chat_command_access,
    extract_chat_command_payload_hints,
)
from features.api.runtime.request_user_resolution import resolve_request_user_id
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.chat.conversation_input_cancellation import (
    prepare_forced_steers_before_cancellation,
)
from features.chat.conversation_stream_cancellation import (
    cancel_conversation_stream_runtime,
    mark_conversation_stream_runtime_cancellation_requested,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "handle_chat_stream_cancel",
    "schedule_ws_chat_stream_cancel",
)


async def handle_chat_stream_cancel(
    data: JSONDict,
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
) -> None:
    hints = extract_chat_command_payload_hints(data)
    conv_id = hints.conv_id
    request_id = hints.request_id
    if not connection_has_chat_command_access(connection):
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="forbidden_error",
            message="Insufficient permissions.",
        )
        return
    if not conv_id:
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="invalid_request_error",
            message="chat_stream_cancel requires a non-empty conv_id.",
        )
        return
    user_id = resolve_request_user_id(request)
    if user_id <= 0:
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="invalid_request_error",
            message="chat_stream_cancel requires an authenticated user_id.",
        )
        return
    connection_user_id_value = (
        connection.user.get("id") if isinstance(connection.user, dict) else None
    )
    if is_strict_int(connection_user_id_value) and int(connection_user_id_value) != int(user_id):
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="forbidden_error",
            message="Insufficient permissions.",
        )
        return
    runtime = await api_context.dependencies.chat_stream_registry.get(
        user_id=user_id,
        conv_id=conv_id,
    )
    if runtime is None:
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="not_found_error",
            message="No active chat stream exists for conv_id.",
        )
        return
    if request_id and runtime.request_id != request_id:
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="not_found_error",
            message="No active chat stream matches request_id.",
        )
        return
    if "intent" in data:
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="invalid_request_error",
            message="chat_stream_cancel no longer accepts intent. Cancellation is stop-only.",
        )
        return
    reason_value = data.get("reason")
    reason = (
        reason_value.strip()
        if isinstance(reason_value, str) and reason_value.strip()
        else "User requested cancellation via WebUI."
    )
    try:
        force_pending_steers = require_bool(
            data.get("force_pending_steers"),
            label="force_pending_steers",
            build_error=ValidationError,
            invalid_message="chat_stream_cancel requires force_pending_steers to be a boolean.",
        )
    except ValidationError as exception:
        await enqueue_chat_stream_command_error(
            connection,
            conv_id=conv_id,
            request_id=request_id,
            phase="cancel",
            code="invalid_request_error",
            message=str(exception),
        )
        return
    if force_pending_steers:
        await prepare_forced_steers_before_cancellation(
            api_context.dependencies,
            user_id=user_id,
            conv_id=conv_id,
            request_id=runtime.request_id,
        )
    mark_conversation_stream_runtime_cancellation_requested(runtime, reason)
    _ = schedule_ws_chat_stream_cancel(
        api_context=api_context,
        context=request.state.context,
        runtime=runtime,
        reason=reason,
    )


def schedule_ws_chat_stream_cancel(
    *,
    api_context: ApiContext,
    context: RequestContext,
    runtime: AssistantTimelineRuntime,
    reason: str,
) -> Task[None]:
    task = create_ephemeral_task(
        cancel_conversation_stream_runtime(
            api_dependencies=api_context.dependencies,
            context=context,
            runtime=runtime,
            reason=reason,
        ),
        name=f"ws-chat-stream-cancel-{runtime.conv_id}",
    )
    api_context.dependencies.application_control.track_background_task(task)
    return task

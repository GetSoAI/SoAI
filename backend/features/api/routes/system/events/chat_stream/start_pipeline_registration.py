"""SoAI - WebSocket chat stream runtime registration [backend/features/api/routes/system/events/chat_stream/start_pipeline_registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import Event
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
)
from core.errors.exceptions import ValidationError
from core.runtime.cancellation_ids import build_chat_stream_task_cancellation_id
from core.timing.monotonic import monotonic_ms
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.api.routes.system.events.chat_stream.start_conflict_resolution import (
    try_register_chat_stream_with_retry,
)
from features.api.routes.system.events.chat_stream.start_pipeline_cleanup import (
    cleanup_failed_ws_chat_stream_start_noncritical,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.runtime_construction import create_chat_stream_runtime

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("ChatStreamStartPipelineFailure", "register_ws_chat_stream_runtime_or_error")

OPERATION_WEBUI_WS_CHAT_STREAM_START_RELEASE_QUOTA = "webui_ws_chat_stream.start.release_quota"


@dataclass(frozen=True, slots=True)
class ChatStreamStartPipelineFailure:
    error_code: str
    error_message: str


async def register_ws_chat_stream_runtime_or_error(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    conv_id: str,
    request_id: str,
    identity: AssistantTurnVariantIdentity,
    user_id: int,
    message_index: int,
    model_id: str | None,
    quota_key_id: str | None,
    quota_token_reservation: JSONDict | None,
    trace_id: str | None,
    logger: LoggerProtocol,
) -> AssistantTimelineRuntime | ChatStreamStartPipelineFailure:
    context = request.state.context
    try:
        context_cancellation_id_value = context.cancellation_id
    except AttributeError:
        context_cancellation_id_value = None
    context_cancellation_id = (
        context_cancellation_id_value.strip()
        if isinstance(context_cancellation_id_value, str)
        else ""
    )
    if not context_cancellation_id:
        await cleanup_failed_ws_chat_stream_start_noncritical(
            logger=logger,
            trace_id=trace_id,
            api_context=api_context,
            chat_streams={},
            runtime=None,
            conv_id=conv_id,
            request_id=request_id,
            placeholder_persisted=False,
            quota_key_id=quota_key_id,
            quota_token_reservation=quota_token_reservation,
            quota_release_operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_RELEASE_QUOTA,
            remove_connection_state=False,
            remove_registry=False,
            release_quota=True,
        )
        return ChatStreamStartPipelineFailure(
            error_code="invalid_request_error",
            error_message="WebSocket request context missing cancellation_id.",
        )
    try:
        task_cancellation_id = build_chat_stream_task_cancellation_id(
            context_cancellation_id=context_cancellation_id,
            request_id=request_id,
        )
    except ValidationError:
        await cleanup_failed_ws_chat_stream_start_noncritical(
            logger=logger,
            trace_id=trace_id,
            api_context=api_context,
            chat_streams={},
            runtime=None,
            conv_id=conv_id,
            request_id=request_id,
            placeholder_persisted=False,
            quota_key_id=quota_key_id,
            quota_token_reservation=quota_token_reservation,
            quota_release_operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_RELEASE_QUOTA,
            remove_connection_state=False,
            remove_registry=False,
            release_quota=True,
        )
        return ChatStreamStartPipelineFailure(
            error_code="invalid_request_error",
            error_message="Chat stream request_id is invalid.",
        )
    runtime = create_chat_stream_runtime(
        conv_id=conv_id,
        request_id=request_id,
        identity=identity,
        user_id=user_id,
        message_index=message_index,
        model_id=model_id,
        task_cancellation_id=task_cancellation_id,
        started_at_monotonic_ms=int(monotonic_ms()),
        detach_event=Event(),
        quota_key_id=quota_key_id,
        quota_token_reservation=quota_token_reservation,
        quota_prompt_tokens=(
            coerce_optional_non_negative_int_strict(
                (
                    quota_token_reservation.get("prompt_tokens")
                    if isinstance(quota_token_reservation, dict)
                    else None
                ),
            )
            if quota_token_reservation is not None
            else None
        ),
    )
    registered = await try_register_chat_stream_with_retry(
        api_context.dependencies.chat_stream_registry,
        runtime,
        timeout_ms=1500,
    )
    if registered:
        return runtime
    await cleanup_failed_ws_chat_stream_start_noncritical(
        logger=logger,
        trace_id=trace_id,
        api_context=api_context,
        chat_streams={},
        runtime=None,
        conv_id=conv_id,
        request_id=request_id,
        placeholder_persisted=False,
        quota_key_id=quota_key_id,
        quota_token_reservation=quota_token_reservation,
        quota_release_operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_RELEASE_QUOTA,
        remove_connection_state=False,
        remove_registry=False,
        release_quota=True,
    )
    return ChatStreamStartPipelineFailure(
        error_code="conflict_error",
        error_message="A chat stream is already active for this conversation.",
    )

"""SoAI - WebSocket chat stream start command handler [backend/features/api/routes/system/events/chat_stream/start_command_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.openai.request_fields import resolve_optional_model_name
from core.openai.stream_request_preparation import (
    OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES,
    build_openai_stream_request_json,
)
from features.agent.runtime.request_message_source import AgenticRequestMessageSource
from features.api.routes.system.events.chat_stream.command_start_request import (
    parse_chat_stream_start_request,
)
from features.api.routes.system.events.chat_stream.start_command_conversation_validation import (
    require_conversation_and_timestamp_ok,
)
from features.api.routes.system.events.chat_stream.start_command_execution import (
    start_chat_stream_runtime,
)
from features.api.routes.system.events.chat_stream.start_command_invalid_request_reporting import (
    report_invalid_start_payload,
)
from features.api.routes.system.events.chat_stream.start_conflict_resolution import (
    ensure_connection_chat_stream_start_allowed,
)
from features.api.routes.system.events.chat_stream.start_failure_finalization import (
    ChatStreamStartFailureBoundary,
    build_chat_stream_start_failure_context,
    finalize_chat_stream_start_failure,
)
from features.api.runtime.chat_prompt_augmentation import (
    build_webui_chat_extra_system_messages,
)
from features.api.runtime.request_user_resolution import resolve_request_user_id
from features.api.runtime.webui_attachments.provider_projection import (
    build_webui_attachment_provider_projector,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("handle_chat_stream_start",)

LOGGER_NAME = "SoAI.features.api.start_command_handler"
OPERATION_WEBUI_WS_CHAT_STREAM_START_PROJECT_ATTACHMENTS = (
    "webui_ws_chat_stream.start.project_attachments"
)


async def handle_chat_stream_start(
    data: JSONDict,
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
    stream_dependencies: StreamDependencies,
    trace_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    parsed_request = await parse_chat_stream_start_request(
        data=data,
        connection=connection,
        logger=logger,
        trace_id=trace_id,
    )
    if parsed_request is None:
        return
    conv_id = parsed_request.conv_id
    request_id = parsed_request.request_id
    identity = parsed_request.identity
    assistant_at_ms = identity.assistant_at_ms
    assistant_turn_at_ms = identity.assistant_turn_at_ms
    openai_request = parsed_request.openai_request
    content_preview_feedback = parsed_request.content_preview_feedback
    preview_contract_feedback = parsed_request.preview_contract_feedback

    chat_streams = connection.chat_streams
    connection_allows_start = await ensure_connection_chat_stream_start_allowed(
        request=request,
        api_context=api_context,
        connection=connection,
        chat_streams=chat_streams,
        conv_id=conv_id,
        request_id=request_id,
    )
    if not connection_allows_start:
        return

    failure_message_index = 0
    failure_model_id = resolve_optional_model_name(openai_request)
    try:
        request_json = build_openai_stream_request_json(
            openai_request=openai_request,
            logger=logger,
            trace_id=trace_id,
            forbidden_fields=OPENAI_STREAM_FORBIDDEN_FIELDS_WITHOUT_MESSAGES,
            conv_id=conv_id,
            messages=None,
        )
    except ValidationError as exception:
        await report_invalid_start_payload(
            connection=connection,
            conv_id=conv_id,
            request_id=request_id,
            logger=logger,
            trace_id=trace_id,
            exception=exception,
        )
        return

    user_id = resolve_request_user_id(request)
    failure_boundary = ChatStreamStartFailureBoundary(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        connection=connection,
        conv_id=conv_id,
        request_id=request_id,
        user_id=user_id,
        model_id=failure_model_id,
    )
    try:
        required_snapshot = await require_conversation_and_timestamp_ok(
            api_context=api_context,
            connection=connection,
            conv_id=conv_id,
            request_id=request_id,
            user_id=user_id,
            assistant_at_ms=assistant_at_ms,
            before_timestamp_exclusive=assistant_turn_at_ms,
            counting_mode="canonical",
            trace_id=trace_id,
            logger=logger,
        )
        if required_snapshot is None:
            return
        snapshot = required_snapshot
        failure_message_index = int(snapshot.message_count)
        model_id = failure_model_id
        canonical_history = list(snapshot.canonical_history)
        project_agentic_prompt_messages = build_webui_attachment_provider_projector(
            dependencies=api_context.dependencies,
            conv_id=conv_id,
            user_id=user_id,
            model_id=model_id,
        )
        request_json["messages"] = await project_agentic_prompt_messages(canonical_history)

        extra_system_messages = build_webui_chat_extra_system_messages(
            persisted_messages=list(snapshot.persisted_messages),
            content_preview_feedback=content_preview_feedback,
            preview_contract_feedback=preview_contract_feedback,
            assistant_turn_at_ms=assistant_turn_at_ms,
        )
        async with api_context.dependencies.conversation_agent_settings_locks.lock(
            (user_id, conv_id),
        ):
            await start_chat_stream_runtime(
                failure_boundary=failure_boundary,
                chat_streams=chat_streams,
                request_json=request_json,
                identity=identity,
                message_count=int(snapshot.message_count),
                extra_system_messages=extra_system_messages,
                agentic_message_source=AgenticRequestMessageSource(
                    canonical_messages=canonical_history,
                    provider_projector=project_agentic_prompt_messages,
                ),
                trace_id=trace_id,
                logger=logger,
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_PROJECT_ATTACHMENTS,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to start delivered conversation input stream.",
            trace_id=trace_id,
            operation=OPERATION_WEBUI_WS_CHAT_STREAM_START_PROJECT_ATTACHMENTS,
            level="warning",
            details={"conv_id": conv_id, "request_id": request_id},
        )
        failure_context = build_chat_stream_start_failure_context(
            boundary=failure_boundary,
            identity=identity,
            message_index=failure_message_index,
        )
        await finalize_chat_stream_start_failure(
            context=failure_context,
            error_code=str(coerced.code),
            error_message=str(coerced),
        )

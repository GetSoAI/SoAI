"""SoAI - WebSocket chat token count command handler [backend/features/api/routes/system/events/websocket_chat_token_count/handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_error
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from features.api.routes.system.events.chat_stream.command_payload_parsing import (
    connection_has_chat_command_access,
    extract_chat_command_payload_hints,
    parse_chat_command_request_fields,
    require_chat_command_json_payload,
    resolve_optional_chat_command_json_array,
    resolve_optional_non_empty_chat_command_text,
)
from features.api.routes.system.events.websocket_chat_token_count.computed_usage_preview import (
    enqueue_counted_usage_preview,
)
from features.api.routes.system.events.websocket_chat_token_count.payloads import (
    enqueue_conversation_not_found_token_count_error,
    enqueue_token_count_error,
)
from features.api.runtime.chat_usage_preview_projection import (
    prepare_chat_usage_preview_request,
)
from features.api.runtime.request_user_resolution import resolve_request_user_id

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("handle_chat_token_count",)

LOGGER_NAME = "SoAI.features.api.handler"
OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_COUNT = "webui_ws_chat_token_count.count"
OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_PREPARE = "webui_ws_chat_token_count.prepare"
OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_VALIDATE = "webui_ws_chat_token_count.validate"


async def handle_chat_token_count(
    data: JSONDict,
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    hints = extract_chat_command_payload_hints(data)
    if not connection_has_chat_command_access(connection):
        await enqueue_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=hints.conv_id,
            request_id=hints.request_id,
            code="forbidden_error",
            message="Insufficient permissions.",
        )
        return
    try:
        payload = require_chat_command_json_payload(data, command_name="chat_token_count")
        fields = parse_chat_command_request_fields(payload)
        draft_user_text = resolve_optional_non_empty_chat_command_text(payload, "draft_user_text")
        draft_attachment_content = resolve_optional_chat_command_json_array(
            payload,
            "draft_attachment_content",
        )
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Invalid WebSocket chat token count payload (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_VALIDATE,
            level="debug",
        )
        await enqueue_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=hints.conv_id,
            request_id=hints.request_id,
            code="invalid_request_error",
            message=str(exception),
        )
        return
    conv_id = fields.conv_id
    request_id = fields.request_id
    openai_request = fields.openai_request

    user_id = resolve_request_user_id(request)
    if user_id <= 0:
        await enqueue_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=conv_id,
            request_id=request_id,
            code="forbidden_error",
            message="Anonymous token count is not supported.",
        )
        return

    database_messages = api_context.dependencies.webui_manager.database_messages
    canonical_history = await database_messages.get_canonical_agent_history(conv_id, user_id)
    if canonical_history is None:
        await enqueue_conversation_not_found_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=conv_id,
            request_id=request_id,
        )
        return

    try:
        prepared_request = await prepare_chat_usage_preview_request(
            request=request,
            api_context=api_context,
            openai_request=openai_request,
            conv_id=conv_id,
            canonical_history=canonical_history,
            draft_user_text=draft_user_text,
            draft_attachment_content=draft_attachment_content,
            logger=logger,
            trace_id=trace_id,
        )
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Token count request failed due to invalid request data (non-critical).",
            trace_id=trace_id,
            operation=OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_PREPARE,
            level="debug",
        )
        await enqueue_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=conv_id,
            request_id=request_id,
            code="invalid_request_error",
            message=str(exception),
        )
        return
    except (AttributeError, KeyError, TypeError, ValueError) as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="webui_ws_chat_token_count.prepare",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Token count request failed.",
            trace_id=trace_id,
            operation=OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_PREPARE,
            level="warning",
        )
        public_error = project_public_error(coerced, trace_id=trace_id)
        await enqueue_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=conv_id,
            request_id=request_id,
            code=str(public_error.code),
            message=public_error.message,
        )
        return

    try:
        await enqueue_counted_usage_preview(
            api_context=api_context,
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            conv_id=conv_id,
            request_id=request_id,
            inference_request_json=prepared_request.inference_request_json,
        )
    except ValidationError as exception:
        log_handled_exception(
            logger,
            exception,
            message=(
                "Token count request failed due to invalid token counting inputs (non-critical)."
            ),
            trace_id=trace_id,
            operation=OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_COUNT,
            level="debug",
            details={"conv_id": conv_id, "request_id": request_id},
        )
        await enqueue_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=conv_id,
            request_id=request_id,
            code="invalid_request_error",
            message=str(exception),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="webui_ws_chat_token_count.count",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Token count request failed.",
            trace_id=trace_id,
            operation=OPERATION_WEBUI_WS_CHAT_TOKEN_COUNT_COUNT,
            level="warning",
            details={"conv_id": conv_id, "request_id": request_id},
        )
        public_error = project_public_error(coerced, trace_id=trace_id)
        await enqueue_token_count_error(
            connection=connection,
            enqueue_warning_tracker=enqueue_warning_tracker,
            trace_id=trace_id,
            conv_id=conv_id,
            request_id=request_id,
            code=str(public_error.code),
            message=public_error.message,
        )

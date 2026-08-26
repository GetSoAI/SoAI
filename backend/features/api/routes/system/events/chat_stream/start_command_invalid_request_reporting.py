"""SoAI - WebSocket chat stream start invalid request reporting [backend/features/api/routes/system/events/chat_stream/start_command_invalid_request_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from features.api.routes.system.events.chat_stream.command_errors import (
    enqueue_chat_stream_start_error,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "report_invalid_start_assistant_at_ms",
    "report_invalid_start_payload",
)

OPERATION_START_VALIDATE_PAYLOAD = "webui_ws_chat_stream.start.validate"
OPERATION_START_ASSISTANT_TIMESTAMP = "webui_ws_chat_stream.start.assistant_at_ms"


async def report_invalid_start_payload(
    *,
    connection: WebsocketConnection,
    conv_id: str,
    request_id: str,
    logger: LoggerProtocol,
    trace_id: str | None,
    exception: ValidationError,
) -> None:
    log_handled_exception(
        logger,
        exception,
        message="Invalid WebSocket chat stream start payload (non-critical).",
        trace_id=trace_id,
        operation=OPERATION_START_VALIDATE_PAYLOAD,
        level="debug",
    )
    await enqueue_chat_stream_start_error(
        connection,
        conv_id,
        request_id,
        "invalid_request_error",
        str(exception),
    )


async def report_invalid_start_assistant_at_ms(
    *,
    connection: WebsocketConnection,
    conv_id: str,
    request_id: str,
    logger: LoggerProtocol,
    trace_id: str | None,
    exception: ValidationError,
) -> None:
    log_handled_exception(
        logger,
        exception,
        message="Invalid assistant timestamp for WebSocket chat stream start (non-critical).",
        trace_id=trace_id,
        operation=OPERATION_START_ASSISTANT_TIMESTAMP,
        level="debug",
    )
    await enqueue_chat_stream_start_error(
        connection,
        conv_id,
        request_id,
        "invalid_request_error",
        str(exception),
    )

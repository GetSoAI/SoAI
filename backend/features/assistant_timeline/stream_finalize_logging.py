"""SoAI - Assistant timeline stream finalization logging [backend/features/assistant_timeline/stream_finalize_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from logging import Logger

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.types.json import JSONDict
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)

__all__ = (
    "chat_stream_terminal_failure_details",
    "log_chat_stream_terminal_status",
)


def _chat_stream_terminal_details(
    context: ChatStreamFinalizeContext,
    *,
    code: str | None = None,
) -> JSONDict:
    details: JSONDict = {
        "conv_id": context.runtime.conv_id,
        "request_id": context.runtime.request_id,
        "assistant_at_ms": context.runtime.assistant_at_ms,
        "user_id": context.runtime.user_id,
        "model_id": context.runtime.model_id,
    }
    if code is not None:
        details["code"] = code
    return details


def chat_stream_terminal_failure_details(context: ChatStreamFinalizeContext) -> JSONDict:
    return {
        "conv_id": context.runtime.conv_id,
        "request_id": context.runtime.request_id,
    }


def log_chat_stream_terminal_status(
    *,
    context: ChatStreamFinalizeContext,
    operation: str,
    logger: Logger,
    normalized_message: str,
    code: str,
    log_message: str,
    level: str,
) -> None:
    log_handled_exception(
        logger,
        coerce_to_soai_error(
            RuntimeError(normalized_message),
            message=normalized_message,
            code=code,
            operation=operation,
            details=_chat_stream_terminal_details(context),
        ),
        message=log_message,
        operation=operation,
        details=_chat_stream_terminal_details(context, code=code),
        level=level,
    )

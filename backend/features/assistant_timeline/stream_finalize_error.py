"""SoAI - Assistant timeline error finalization [backend/features/assistant_timeline/stream_finalize_error.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.stream_finalize_logging import (
    log_chat_stream_terminal_status,
)
from features.assistant_timeline.stream_terminal_error_completion import (
    complete_claimed_chat_stream_error,
)
from features.assistant_timeline.stream_terminal_executor import (
    run_chat_stream_terminal_finalization,
)

__all__ = ("finalize_chat_stream_error",)

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_finalize_error"
OPERATION_ERROR = "webui_ws_chat_stream.finalize.error"


async def finalize_chat_stream_error(
    context: ChatStreamFinalizeContext,
    *,
    message: str,
    code: str,
    flush_deferred_visible_text: bool = True,
) -> bool:
    async def finalize_claimed() -> None:
        normalized_message = message.strip() if message.strip() else "Chat stream failed."
        normalized_code = code.strip() if code.strip() else "server_error"
        log_chat_stream_terminal_status(
            context=context,
            operation=OPERATION_ERROR,
            logger=get_logger(LOGGER_NAME),
            normalized_message=normalized_message,
            code=normalized_code,
            log_message="Chat stream finalized with error (non-critical).",
            level="debug",
        )
        await complete_claimed_chat_stream_error(
            context=context,
            message=normalized_message,
            code=normalized_code,
            flush_deferred_visible_text=flush_deferred_visible_text,
        )

    return await run_chat_stream_terminal_finalization(
        context=context,
        operation=OPERATION_ERROR,
        logger=get_logger(LOGGER_NAME),
        failure_message="Failed to finalize chat stream error.",
        terminal_outcome="error",
        finalize_claimed=finalize_claimed,
    )

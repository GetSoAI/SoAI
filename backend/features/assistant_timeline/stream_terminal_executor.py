"""SoAI - Assistant timeline terminal finalization executor [backend/features/assistant_timeline/stream_terminal_executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from features.assistant_timeline.stream_finalize_logging import (
    chat_stream_terminal_failure_details,
)
from features.assistant_timeline.stream_terminal_failure_persistence import (
    mark_chat_stream_terminal_failure_detached,
    persist_chat_stream_terminal_failure_state,
)
from features.assistant_timeline.stream_terminal_lifecycle import (
    begin_chat_stream_terminal_finalization,
    fail_chat_stream_terminal_finalization,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.assistant_timeline.stream_finalize_context import (
        ChatStreamFinalizeContext,
    )

__all__ = ("run_chat_stream_terminal_finalization",)


async def run_chat_stream_terminal_finalization(
    *,
    context: ChatStreamFinalizeContext,
    operation: str,
    logger: LoggerProtocol,
    failure_message: str,
    finalize_claimed: Callable[[], Awaitable[None]],
) -> bool:
    if not await begin_chat_stream_terminal_finalization(context):
        return False
    try:
        await finalize_claimed()
        return True
    except CancelledError:
        await uncancel_then_cleanup(fail_chat_stream_terminal_finalization(context))
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        await fail_chat_stream_terminal_finalization(context)
        coerced = coerce_to_soai_error(
            exception,
            operation=operation,
        )
        log_exception(
            logger,
            coerced,
            operation=operation,
            message=failure_message,
            trace_id=None,
            details=chat_stream_terminal_failure_details(context),
        )
        try:
            await persist_chat_stream_terminal_failure_state(
                context=context,
                terminal_reason=str(coerced),
            )
        except HANDLED_RUNTIME_EXCEPTIONS as fallback_exception:
            fallback_error = coerce_to_soai_error(
                fallback_exception,
                operation=operation,
            )
            log_exception(
                logger,
                fallback_error,
                operation=operation,
                message="Chat stream terminal failure persistence failed.",
                trace_id=None,
                details=chat_stream_terminal_failure_details(context),
            )
            await mark_chat_stream_terminal_failure_detached(context=context)
        return True

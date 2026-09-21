"""SoAI - Assistant timeline terminal finalization executor [backend/features/assistant_timeline/stream_terminal_executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from features.assistant_timeline.stream_finalize_logging import (
    chat_stream_terminal_failure_details,
)
from features.assistant_timeline.stream_terminal_error_completion import (
    complete_claimed_chat_stream_error,
)
from features.assistant_timeline.stream_terminal_lifecycle import (
    begin_chat_stream_terminal_finalization,
    complete_chat_stream_terminal_finalization,
    fail_chat_stream_terminal_finalization,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.assistant_timeline.stream_finalize_context import (
        ChatStreamFinalizeContext,
    )

__all__ = ("run_chat_stream_terminal_finalization",)


async def _settle_cancelled_terminal_finalization(
    context: ChatStreamFinalizeContext,
) -> None:
    if context.runtime.terminal_persistence_completed:
        await uncancel_then_cleanup(
            complete_chat_stream_terminal_finalization(context),
        )
        return
    await uncancel_then_cleanup(fail_chat_stream_terminal_finalization(context))


async def _complete_durable_terminal_after_failure(
    *,
    context: ChatStreamFinalizeContext,
    exception: Exception,
    operation: str,
    logger: LoggerProtocol,
) -> bool:
    if not context.runtime.terminal_persistence_completed:
        return False
    coerced = coerce_to_soai_error(exception, operation=operation)
    log_exception(
        logger,
        coerced,
        operation=operation,
        message="Chat stream terminal preparation or delivery failed after durable finalization.",
        trace_id=None,
        details=chat_stream_terminal_failure_details(context),
    )
    await uncancel_then_cleanup(complete_chat_stream_terminal_finalization(context))
    return True


async def run_chat_stream_terminal_finalization(
    *,
    context: ChatStreamFinalizeContext,
    operation: str,
    logger: LoggerProtocol,
    failure_message: str,
    terminal_outcome: Literal["cancelled", "completed", "error"],
    finalize_claimed: Callable[[], Awaitable[None]],
) -> bool:
    if not await begin_chat_stream_terminal_finalization(context, terminal_outcome):
        return False
    try:
        await finalize_claimed()
        return True
    except CancelledError:
        await _settle_cancelled_terminal_finalization(context)
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if await _complete_durable_terminal_after_failure(
            context=context,
            exception=exception,
            operation=operation,
            logger=logger,
        ):
            return True
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
        if context.runtime.terminal_persistence_attempted:
            raise
        if terminal_outcome == "cancelled":
            raise
        if not await begin_chat_stream_terminal_finalization(context, "error"):
            raise StateError(
                "Chat stream terminal failure recovery claim is unavailable.",
            ) from exception
        try:
            await complete_claimed_chat_stream_error(
                context=context,
                message="Chat stream failed.",
                code="server_error",
                flush_deferred_visible_text=False,
            )
        except CancelledError:
            await _settle_cancelled_terminal_finalization(context)
            raise
        except HANDLED_RUNTIME_EXCEPTIONS as fallback_exception:
            if await _complete_durable_terminal_after_failure(
                context=context,
                exception=fallback_exception,
                operation=operation,
                logger=logger,
            ):
                return True
            await fail_chat_stream_terminal_finalization(context)
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
            raise
        return True

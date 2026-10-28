"""SoAI - Playwright cleanup failure ownership [backend/core/browser/playwright_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable

from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    uncancel_then_cleanup,
)
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger

__all__ = (
    "await_playwright_caller_cleanup",
    "finish_playwright_close_stage",
    "preserve_playwright_primary_failure",
)

LOGGER_NAME = "SoAI.core.browser.playwright_cleanup"
OPERATION_CLEANUP = "core.browser.playwright_cleanup.close"


def preserve_playwright_primary_failure(
    primary_exception: BaseException | None, cleanup_exception: BaseException | None
) -> None:
    if (
        primary_exception is not None
        and cleanup_exception is not None
        and cleanup_exception is not primary_exception
    ):
        raise primary_exception from primary_exception.__cause__


async def finish_playwright_close_stage(
    cleanup: Awaitable[None],
    primary_exception: BaseException | None,
    *,
    already_reported_failure: Callable[[], BaseException | None],
    cleanup_action: str,
) -> None:
    try:
        await cleanup
    except asyncio.CancelledError:
        if primary_exception is None:
            raise
        primary_exception.add_note(f"{cleanup_action} was cancelled.")
        raise primary_exception from primary_exception.__cause__
    except Exception as cleanup_exception:
        if already_reported_failure() is not cleanup_exception:
            log_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(cleanup_exception, operation=OPERATION_CLEANUP),
                message=f"{cleanup_action} failed.",
                operation=OPERATION_CLEANUP,
            )
        if primary_exception is None:
            raise
        primary_exception.add_note(f"{cleanup_action} failed: {cleanup_exception}")
        raise primary_exception from primary_exception.__cause__


async def await_playwright_caller_cleanup(cleanup: Awaitable[None]) -> None:
    try:
        await uncancel_then_cleanup(cleanup)
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    finally:
        cleanup_exception = sys.exception()
        if isinstance(cleanup_exception, Exception) and current_task_has_pending_cancellation():
            raise asyncio.CancelledError() from cleanup_exception

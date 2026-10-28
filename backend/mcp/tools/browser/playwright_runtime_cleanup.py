"""SoAI - Playwright runtime cleanup flows [backend/mcp/tools/browser/playwright_runtime_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.browser.playwright_cleanup import preserve_playwright_primary_failure
from core.browser.playwright_driver_errors import PlaywrightDriverConnectionClosedError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.constants import CONTROL_TIMEOUT_SEC
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.playwright_runtime_shutdown import (
    close_browser_with_logging,
    stop_playwright_with_logging,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser

    from core.browser.playwright_lifecycle import PlaywrightDriverSession
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONValue

__all__ = (
    "cleanup_disconnected_playwright_driver",
    "shutdown_playwright_runtime",
)

_OPERATION_DRIVER_DISCONNECT_CLEANUP = "mcp.browser.playwright_runtime.driver_disconnect_cleanup"
_OPERATION_RUNTIME_SHUTDOWN = "mcp.browser.playwright_runtime.shutdown"
_DRIVER_DISCONNECT_CLEANUP_EXCEPTIONS: tuple[type[Exception], ...] = (
    Error,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


async def cleanup_disconnected_playwright_driver(
    *,
    playwright: PlaywrightDriverSession,
    browsers: list[Browser],
    logger: LoggerProtocol,
    notifier: Callable[[], Awaitable[None]] | None,
    primary_exception: PlaywrightDriverConnectionClosedError,
) -> None:
    try:
        await uncancel_then_cleanup(
            asyncio.wait_for(
                _close_disconnected_playwright_driver(
                    playwright=playwright,
                    browsers=browsers,
                    logger=logger,
                    notifier=notifier,
                ),
                timeout=CONTROL_TIMEOUT_SEC,
            ),
        )
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except _DRIVER_DISCONNECT_CLEANUP_EXCEPTIONS as cleanup_exception:
        primary_exception.add_note(
            f"Playwright driver disconnect cleanup failed: {cleanup_exception}"
        )
        raise primary_exception from cleanup_exception


async def _close_disconnected_playwright_driver(
    *,
    playwright: PlaywrightDriverSession,
    browsers: list[Browser],
    logger: LoggerProtocol,
    notifier: Callable[[], Awaitable[None]] | None,
) -> None:
    seen_browser_ids: set[int] = set()
    details: dict[str, JSONValue] = {"driver": "playwright"}
    if notifier is not None:
        try:
            await notifier()
        except asyncio.CancelledError as exception:
            raise_cancelled_error(exception)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_exception(
                logger,
                coerce_to_soai_error(
                    exception,
                    operation=_OPERATION_DRIVER_DISCONNECT_CLEANUP,
                ),
                message="Failed to notify browser sessions of Playwright driver disconnect.",
                operation=_OPERATION_DRIVER_DISCONNECT_CLEANUP,
                details=details,
            )
    for browser in browsers:
        browser_id = id(browser)
        if browser_id in seen_browser_ids:
            continue
        seen_browser_ids.add(browser_id)
        try:
            await close_browser_with_logging(browser, logger=logger)
        except asyncio.CancelledError as exception:
            raise_cancelled_error(exception)
        except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=_OPERATION_DRIVER_DISCONNECT_CLEANUP,
                details=details,
            )
            log_exception(
                logger,
                coerced,
                message="Failed to close Playwright browser during driver disconnect cleanup.",
                operation=_OPERATION_DRIVER_DISCONNECT_CLEANUP,
                details=details,
                level="warning",
            )
    await stop_playwright_with_logging(playwright, logger=logger)


async def shutdown_playwright_runtime(
    *,
    playwright: PlaywrightDriverSession | None,
    browsers: list[Browser],
    logger: LoggerProtocol,
) -> None:
    primary_exception: Exception | None = None
    details: dict[str, JSONValue] = {"driver": "playwright"}
    for browser in browsers:
        try:
            await close_browser_with_logging(browser, logger=logger)
        except asyncio.CancelledError as exception:
            raise_cancelled_error(exception)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            if not isinstance(exception, PLAYWRIGHT_OPERATION_EXCEPTIONS):
                if primary_exception is None:
                    primary_exception = exception
            else:
                coerced = coerce_to_soai_error(
                    exception,
                    operation=_OPERATION_RUNTIME_SHUTDOWN,
                    details=details,
                )
                log_exception(
                    logger,
                    coerced,
                    message="Failed to close Playwright browser during runtime shutdown.",
                    operation=_OPERATION_RUNTIME_SHUTDOWN,
                    details=details,
                    level="warning",
                )
                if primary_exception is None:
                    primary_exception = exception
    if playwright is not None:
        try:
            await stop_playwright_with_logging(playwright, logger=logger)
        finally:
            preserve_playwright_primary_failure(primary_exception, sys.exception())
    if primary_exception is not None:
        raise primary_exception

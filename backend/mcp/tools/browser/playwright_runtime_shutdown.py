"""SoAI - Playwright runtime shutdown helpers [backend/mcp/tools/browser/playwright_runtime_shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from mcp.tools.browser.playwright_driver_errors import (
    classify_playwright_driver_connection_closed_exception,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright

    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONValue

__all__ = (
    "close_browser_context_with_logging",
    "close_browser_with_logging",
    "stop_playwright_with_logging",
)

_OPERATION_CLOSE_BROWSER = "mcp.browser.playwright_runtime.shutdown.close_browser"
_OPERATION_CLOSE_CONTEXT = "mcp.browser.playwright_runtime.shutdown.close_context"
_OPERATION_STOP_PLAYWRIGHT = "mcp.browser.playwright_runtime.shutdown.stop_playwright"
_PLAYWRIGHT_SHUTDOWN_EXCEPTIONS: tuple[type[Exception], ...] = (
    Error,
    *RECOVERABLE_EXCEPTIONS,
)


def _log_playwright_shutdown_exception(
    logger: LoggerProtocol,
    exception: Exception,
    *,
    operation: str,
    recoverable_message: str,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    coerced = coerce_to_soai_error(exception, operation=operation)
    log_handled_exception(
        logger,
        coerced,
        message=recoverable_message,
        operation=operation,
        details=details,
        level="debug",
    )


async def close_browser_with_logging(
    browser: Browser,
    *,
    logger: LoggerProtocol,
) -> None:
    try:
        if not browser.is_connected():
            logger.debug("Playwright browser already disconnected; skipping close.")
            return
        await browser.close()
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except _PLAYWRIGHT_SHUTDOWN_EXCEPTIONS as exception:
        driver_error = classify_playwright_driver_connection_closed_exception(
            exception,
            operation=_OPERATION_CLOSE_BROWSER,
            details={},
        )
        if driver_error is not None:
            coerced = coerce_to_soai_error(
                driver_error,
                operation=_OPERATION_CLOSE_BROWSER,
            )
            log_exception(
                logger,
                coerced,
                message="Playwright browser close failed because the driver connection was already closed (non-critical).",
                operation=_OPERATION_CLOSE_BROWSER,
                level="debug",
            )
            return
        if not isinstance(exception, _PLAYWRIGHT_SHUTDOWN_EXCEPTIONS):
            raise
        _log_playwright_shutdown_exception(
            logger,
            exception,
            operation=_OPERATION_CLOSE_BROWSER,
            recoverable_message="Failed to close Playwright browser during shutdown (non-critical).",
        )


async def stop_playwright_with_logging(
    playwright: Playwright,
    *,
    logger: LoggerProtocol,
) -> None:
    try:
        await playwright.stop()
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except _PLAYWRIGHT_SHUTDOWN_EXCEPTIONS as exception:
        driver_error = classify_playwright_driver_connection_closed_exception(
            exception,
            operation=_OPERATION_STOP_PLAYWRIGHT,
            details={},
        )
        if driver_error is not None:
            coerced = coerce_to_soai_error(
                driver_error,
                operation=_OPERATION_STOP_PLAYWRIGHT,
            )
            log_exception(
                logger,
                coerced,
                message="Playwright stop failed because the driver connection was already closed (non-critical).",
                operation=_OPERATION_STOP_PLAYWRIGHT,
                level="debug",
            )
            return
        if not isinstance(exception, _PLAYWRIGHT_SHUTDOWN_EXCEPTIONS):
            raise
        _log_playwright_shutdown_exception(
            logger,
            exception,
            operation=_OPERATION_STOP_PLAYWRIGHT,
            recoverable_message="Failed to stop Playwright during shutdown (non-critical).",
        )


async def close_browser_context_with_logging(
    context: BrowserContext,
    *,
    logger: LoggerProtocol,
    operation: str = _OPERATION_CLOSE_CONTEXT,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    try:
        await context.close()
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except _PLAYWRIGHT_SHUTDOWN_EXCEPTIONS as exception:
        driver_error = classify_playwright_driver_connection_closed_exception(
            exception,
            operation=operation,
            details=details or {},
        )
        if driver_error is not None:
            coerced = coerce_to_soai_error(driver_error, operation=operation)
            log_exception(
                logger,
                coerced,
                message="Playwright context close failed because the driver connection was already closed (non-critical).",
                operation=operation,
                details=details,
                level="debug",
            )
            return
        if not isinstance(exception, _PLAYWRIGHT_SHUTDOWN_EXCEPTIONS):
            raise
        _log_playwright_shutdown_exception(
            logger,
            exception,
            operation=operation,
            recoverable_message="Failed to close Playwright browser context during shutdown (non-critical).",
            details=details,
        )

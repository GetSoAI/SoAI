"""SoAI - Playwright driver call guards [backend/mcp/tools/browser/playwright_driver_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from typing import TYPE_CHECKING

from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from mcp.tools.browser.playwright_driver_errors import (
    classify_playwright_driver_connection_closed_exception,
)
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONValue

__all__ = ("await_playwright_driver_call",)


async def await_playwright_driver_call[DriverResult](
    pending: Awaitable[DriverResult],
    *,
    operation: str,
    logger: LoggerProtocol,
    details: Mapping[str, JSONValue],
    failure_message: str,
) -> DriverResult:
    try:
        return await pending
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
        driver_error = classify_playwright_driver_connection_closed_exception(
            exception,
            operation=operation,
            details=details,
        )
        if driver_error is None:
            raise
        coerced = coerce_to_soai_error(driver_error, operation=operation)
        log_exception(
            logger,
            coerced,
            message=failure_message,
            operation=operation,
            details=details,
            level="warning",
        )
        raise driver_error from exception

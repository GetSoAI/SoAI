"""SoAI - Playwright driver error classification [backend/mcp/tools/browser/playwright_driver_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ServiceUnavailableError

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "PlaywrightDriverConnectionClosedError",
    "build_playwright_driver_connection_closed_error",
    "classify_playwright_driver_connection_closed_exception",
    "is_playwright_driver_connection_closed",
)

_DRIVER_CONNECTION_CLOSED_SIGNATURE = "connection closed while reading from the driver"


class PlaywrightDriverConnectionClosedError(ServiceUnavailableError):
    code: str | int = "playwright_driver_connection_closed"


def is_playwright_driver_connection_closed(exception: BaseException) -> bool:
    return _DRIVER_CONNECTION_CLOSED_SIGNATURE in str(exception).lower()


def build_playwright_driver_connection_closed_error(
    exception: Exception,
    *,
    operation: str,
    details: Mapping[str, JSONValue],
) -> PlaywrightDriverConnectionClosedError:
    return PlaywrightDriverConnectionClosedError(
        "Playwright driver connection closed while communicating with browser automation.",
        operation=operation,
        cause=exception,
        details=details,
    )


def classify_playwright_driver_connection_closed_exception(
    exception: Exception,
    *,
    operation: str,
    details: Mapping[str, JSONValue],
) -> PlaywrightDriverConnectionClosedError | None:
    if isinstance(exception, PlaywrightDriverConnectionClosedError):
        return exception
    if not is_playwright_driver_connection_closed(exception):
        return None
    return build_playwright_driver_connection_closed_error(
        exception,
        operation=operation,
        details=details,
    )

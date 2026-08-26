"""SoAI - Playwright operation exception contract [backend/mcp/tools/browser/playwright_operation_exceptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from playwright.async_api import Error

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from mcp.tools.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
)

__all__ = ("PLAYWRIGHT_OPERATION_EXCEPTIONS",)

PLAYWRIGHT_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    PlaywrightDriverConnectionClosedError,
    Error,
    *RECOVERABLE_EXCEPTIONS,
)

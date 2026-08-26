"""SoAI - Browser page metadata helpers [backend/mcp/tools/browser/page_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from playwright.async_api import Error

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.logging.trace import get_logger
from mcp.tools.browser.internal_protocols import BrowserPageProtocol
from mcp.tools.browser.page_retry_policy import wait_for_page_recovery
from mcp.tools.browser.playwright_error_classification import (
    is_execution_context_destroyed_error,
)

__all__ = ("safe_page_title",)

OPERATION_MCP_BROWSER_SAFE_PAGE_TITLE = "mcp_browser.safe_page_title"

BROWSER_PAGE_TITLE_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (Error,)
LOGGER_NAME = "SoAI.mcp.tools.page_metadata"


async def safe_page_title(
    page: BrowserPageProtocol,
    *,
    timeout_ms: int,
    retries: int,
    delay_ms: int,
) -> str:
    logger = get_logger(LOGGER_NAME)
    effective_timeout_ms = max(1, int(timeout_ms))
    attempts = max(0, int(retries))
    delay = max(0, int(delay_ms))
    for attempt in range(attempts + 1):
        try:
            async with asyncio.timeout(float(effective_timeout_ms) / 1000.0):
                title = await _resolve_page_title(page.title())
            return title if isinstance(title, str) else str(title)
        except BROWSER_PAGE_TITLE_RETRY_EXCEPTIONS as exception:
            error = coerce_to_soai_error(
                exception,
                operation=OPERATION_MCP_BROWSER_SAFE_PAGE_TITLE,
            )
            if not is_execution_context_destroyed_error(exception):
                log_exception(
                    logger,
                    error,
                    message="Browser page title resolution failed.",
                    operation=OPERATION_MCP_BROWSER_SAFE_PAGE_TITLE,
                    level="warning",
                )
                raise error from exception
            log_handled_exception(
                logger,
                error,
                message=(
                    "Browser execution context destroyed while resolving "
                    "page title (non-critical)."
                ),
                operation=OPERATION_MCP_BROWSER_SAFE_PAGE_TITLE,
                level="debug",
            )
            if attempt >= attempts:
                return ""
            await wait_for_page_recovery(
                page,
                timeout_ms=effective_timeout_ms,
                delay_ms=delay,
                logger=logger,
                operation=OPERATION_MCP_BROWSER_SAFE_PAGE_TITLE,
                action_label="title",
            )
        except TimeoutError as exception:
            error = coerce_to_soai_error(
                exception,
                operation=OPERATION_MCP_BROWSER_SAFE_PAGE_TITLE,
            )
            log_exception(
                logger,
                error,
                message="Browser page title resolution timed out.",
                operation=OPERATION_MCP_BROWSER_SAFE_PAGE_TITLE,
                level="warning",
            )
            raise error from exception
    return ""


async def _resolve_page_title(value: str | Awaitable[str]) -> str:
    if isinstance(value, str):
        return value
    return await value

"""SoAI - Browser page retry policy [backend/mcp/tools/browser/page_retry_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from playwright.async_api import Error

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.logging.protocols import LoggerProtocol
from mcp.tools.browser.internal_protocols import BrowserPageProtocol

__all__ = ("wait_for_page_recovery",)

OPERATION_MCP_TOOLS_BROWSER_PAGE_RETRY_WAIT_FOR_LOAD_STATE = (
    "mcp.tools.browser.page_retry_policy.wait_for_load_state"
)
OPERATION_MCP_TOOLS_BROWSER_PAGE_RETRY_WAIT_FOR_TIMEOUT = (
    "mcp.tools.browser.page_retry_policy.wait_for_timeout"
)


async def wait_for_page_recovery(
    page: BrowserPageProtocol,
    *,
    timeout_ms: int,
    delay_ms: int,
    logger: LoggerProtocol,
    operation: str,
    action_label: str,
) -> None:
    per_try_timeout_ms = min(2000, max(1, int(timeout_ms)))
    try:
        async with asyncio.timeout(float(per_try_timeout_ms) / 1000.0):
            await _await_none_result(page.wait_for_load_state("domcontentloaded"))
    except (Error, TimeoutError) as wait_error:
        error = coerce_to_soai_error(
            wait_error,
            operation=(OPERATION_MCP_TOOLS_BROWSER_PAGE_RETRY_WAIT_FOR_LOAD_STATE),
        )
        log_handled_exception(
            logger,
            error,
            message=(
                "Failed to wait for browser load state during "
                f"{action_label} retry (non-critical)."
            ),
            operation=operation,
            level="debug",
        )
    if delay_ms <= 0:
        return
    try:
        async with asyncio.timeout(float(per_try_timeout_ms) / 1000.0):
            await _await_none_result(page.wait_for_timeout(max(0, int(delay_ms))))
    except (Error, TimeoutError) as wait_error:
        error = coerce_to_soai_error(
            wait_error,
            operation=OPERATION_MCP_TOOLS_BROWSER_PAGE_RETRY_WAIT_FOR_TIMEOUT,
        )
        log_handled_exception(
            logger,
            error,
            message=(
                "Failed to wait for browser timeout during " f"{action_label} retry (non-critical)."
            ),
            operation=operation,
            level="debug",
        )


async def _await_none_result(value: None | Awaitable[None]) -> None:
    if value is None:
        return
    await value

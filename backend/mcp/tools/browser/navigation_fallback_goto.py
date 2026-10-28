"""SoAI - Browser primary and http-fallback navigation gotos awaiting the Chromium error-page commit [backend/mcp/tools/browser/navigation_fallback_goto.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from mcp.tools.browser.playwright_error_classification import (
    is_chrome_internal_error_url,
    resolve_chromium_net_error_code,
)
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)

if TYPE_CHECKING:
    from playwright.async_api import Frame, Page

    from mcp.tools.browser.argument_validation import PageWaitUntil

__all__ = (
    "goto_awaiting_error_page_commit",
    "goto_with_http_fallback",
)

_ABORTED_NET_ERROR_CODE = "ERR_ABORTED"


async def goto_awaiting_error_page_commit(
    page: Page,
    url: str,
    *,
    wait_until: PageWaitUntil,
    timeout: int | None,
) -> None:
    error_page_committed = asyncio.Event()

    def _record_error_page_commit(frame: Frame) -> None:
        if frame.parent_frame is None and is_chrome_internal_error_url(frame.url):
            error_page_committed.set()

    page.on("framenavigated", _record_error_page_commit)
    try:
        await page.goto(url, wait_until=wait_until, timeout=timeout)
    except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
        if _commits_error_page(exception):
            await _await_error_page_commit(error_page_committed)
        raise
    finally:
        page.remove_listener("framenavigated", _record_error_page_commit)


async def goto_with_http_fallback(
    page: Page,
    *,
    primary_url: str,
    fallback_url: str | None,
    wait_until: PageWaitUntil,
    timeout: int,
    enforce_fallback_policy: Callable[[str], Awaitable[None]],
) -> None:
    try:
        await goto_awaiting_error_page_commit(
            page,
            primary_url,
            wait_until=wait_until,
            timeout=timeout,
        )
    except (Error, TimeoutError):
        if fallback_url is None:
            raise
        await enforce_fallback_policy(fallback_url)
        await goto_awaiting_error_page_commit(
            page,
            fallback_url,
            wait_until=wait_until,
            timeout=timeout,
        )


def _commits_error_page(exception: BaseException) -> bool:
    net_error_code = resolve_chromium_net_error_code(exception)
    return net_error_code is not None and net_error_code != _ABORTED_NET_ERROR_CODE


async def _await_error_page_commit(error_page_committed: asyncio.Event) -> None:
    try:
        async with asyncio.timeout(LOCAL_IO_TIMEOUT_SEC):
            await error_page_committed.wait()
    except TimeoutError:
        return

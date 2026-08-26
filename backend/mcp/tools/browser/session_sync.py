"""SoAI - Browser session synchronization helpers [backend/mcp/tools/browser/session_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from playwright.async_api import Page

from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.config.protocols import ConfigProtocol
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC
from mcp.tools.browser.config_values import resolve_browser_max_concurrent_pages
from mcp.tools.browser.page_ref_state import prune_page_ref_states
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.session_config import apply_page_timeouts, attach_page_handlers
from mcp.tools.browser.session_event_queues import drain_event_queues
from mcp.tools.browser.session_state import (
    mark_browser_session_from_playwright_exception,
)
from mcp.tools.browser.types import BrowserSessionState
from mcp.tools.error import MCPToolError

__all__ = (
    "install_context_page_tracking",
    "sync_session_state",
)

OPERATION_MCP_BROWSER_SESSION_SYNC_CLOSE_EXCESS_PAGES_CLOSE_PAGE = (
    "mcp.browser.session_sync.close_excess_pages.close_page"
)


LOGGER_NAME = "SoAI.mcp.tools.session_sync"


def install_context_page_tracking(_config: ConfigProtocol, state: BrowserSessionState) -> None:
    def _on_page(page: Page) -> None:
        _ = put_nowait_with_overwrite(state.page_open_queue, page, overwrite_attempts=1)

    state.context.on("page", _on_page)


async def sync_session_state(
    config: ConfigProtocol,
    state: BrowserSessionState,
    *,
    enforce_page_limit: bool = False,
    downloads_dir: str | None = None,
    desired_active_page: Page | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    drain_event_queues(
        config,
        state,
        downloads_dir=downloads_dir,
    )

    opened_pages: list[Page] = []
    while True:
        try:
            opened_pages.append(state.page_open_queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    for page in opened_pages:
        if page.is_closed():
            continue
        page_id = id(page)
        if page_id in state.known_page_ids:
            continue
        attach_page_handlers(config, state, page)
        apply_page_timeouts(config, page)
        state.known_page_ids.add(page_id)

    while True:
        try:
            _ = state.page_close_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    try:
        raw_pages_before = list(state.context.pages)
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except PLAYWRIGHT_OPERATION_EXCEPTIONS as context_error:
        mark_browser_session_from_playwright_exception(
            state,
            exception=context_error,
        )
        if not state.context_closed:
            raise
        raise MCPToolError(
            -32603,
            "Browser context has closed. A new session will be created automatically on your next browser_navigate call.",
        ) from context_error
    context_pages_before = [page for page in raw_pages_before if not page.is_closed()]
    for page in context_pages_before:
        page_id = id(page)
        if page_id in state.known_page_ids:
            continue
        attach_page_handlers(config, state, page)
        apply_page_timeouts(config, page)
        state.known_page_ids.add(page_id)

    previous_active_index = int(state.active_index)
    previous_active_page: Page | None = None
    if state.pages and 0 <= previous_active_index < len(state.pages):
        previous_candidate = state.pages[previous_active_index]
        if not previous_candidate.is_closed():
            previous_active_page = previous_candidate

    protected_active_page: Page | None = None
    if desired_active_page is not None and desired_active_page in context_pages_before:
        protected_active_page = desired_active_page
    elif previous_active_page is not None and previous_active_page in context_pages_before:
        protected_active_page = previous_active_page

    state.pages = context_pages_before
    if enforce_page_limit:
        max_pages = resolve_browser_max_concurrent_pages(config)
    else:
        max_pages = len(state.pages)

    if len(state.pages) > max_pages:
        to_close: list[Page] = []
        for page in reversed(state.pages):
            if len(state.pages) - len(to_close) <= max_pages:
                break
            if protected_active_page is not None and page is protected_active_page:
                continue
            to_close.append(page)
        for page in to_close:
            try:
                await asyncio.wait_for(page.close(), timeout=CONTROL_TIMEOUT_SEC)
            except asyncio.CancelledError as exception:
                raise_cancelled_error(exception)
            except TimeoutError as exception:
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_MCP_BROWSER_SESSION_SYNC_CLOSE_EXCESS_PAGES_CLOSE_PAGE,
                )
                log_handled_exception(
                    logger,
                    coerced,
                    message="Failed to close excess browser tab during session sync (non-critical).",
                    operation=OPERATION_MCP_BROWSER_SESSION_SYNC_CLOSE_EXCESS_PAGES_CLOSE_PAGE,
                    details={},
                    level="debug",
                )
                continue
            except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
                mark_browser_session_from_playwright_exception(
                    state,
                    exception=exception,
                )
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_MCP_BROWSER_SESSION_SYNC_CLOSE_EXCESS_PAGES_CLOSE_PAGE,
                )
                log_handled_exception(
                    logger,
                    coerced,
                    message="Failed to close excess browser tab during session sync (non-critical).",
                    operation=OPERATION_MCP_BROWSER_SESSION_SYNC_CLOSE_EXCESS_PAGES_CLOSE_PAGE,
                    details={},
                    level="debug",
                )
                continue

    try:
        raw_pages_after = list(state.context.pages)
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except PLAYWRIGHT_OPERATION_EXCEPTIONS as context_error:
        mark_browser_session_from_playwright_exception(
            state,
            exception=context_error,
        )
        if not state.context_closed:
            raise
        raise MCPToolError(
            -32603,
            "Browser context has closed. A new session will be created automatically on your next browser_navigate call.",
        ) from context_error
    context_pages_after = [page for page in raw_pages_after if not page.is_closed()]
    if not context_pages_after:
        try:
            page = await state.context.new_page()
        except asyncio.CancelledError as exception:
            raise_cancelled_error(exception)
        except PLAYWRIGHT_OPERATION_EXCEPTIONS as new_page_error:
            mark_browser_session_from_playwright_exception(
                state,
                exception=new_page_error,
            )
            if not state.context_closed:
                raise
            raise MCPToolError(
                -32603,
                "Browser context has closed. A new session will be created automatically on your next browser_navigate call.",
            ) from new_page_error
        attach_page_handlers(config, state, page)
        apply_page_timeouts(config, page)
        context_pages_after = [page]
    state.pages = context_pages_after
    state.known_page_ids = {id(page) for page in context_pages_after}
    prune_page_ref_states(state, state.known_page_ids)
    active_page_after: Page | None = None
    if desired_active_page is not None and desired_active_page in context_pages_after:
        active_page_after = desired_active_page
    elif previous_active_page is not None and previous_active_page in context_pages_after:
        active_page_after = previous_active_page
    else:
        stable_index = max(0, previous_active_index)
        stable_index = min(stable_index, len(context_pages_after) - 1)
        active_page_after = context_pages_after[stable_index]
    state.active_index = context_pages_after.index(active_page_after)

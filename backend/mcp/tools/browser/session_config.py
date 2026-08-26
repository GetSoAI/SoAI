"""SoAI - Browser session configuration [backend/mcp/tools/browser/session_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from mcp.tools.browser.config_values import (
    browser_bool,
    browser_min_int,
    resolve_browser_dns_timeout_sec,
)
from mcp.tools.browser.session_event_handlers import (
    make_console_handler,
    make_dialog_handler,
    make_download_handler,
    make_page_close_handler,
    make_route_handler,
    make_websocket_route_handler,
)
from mcp.tools.browser.session_network_events import (
    make_request_failed_handler,
    make_response_handler,
)
from mcp.tools.browser.types import BrowserSessionState

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.config.protocols import ConfigProtocol

__all__ = (
    "attach_context_handlers",
    "apply_page_timeouts",
    "attach_page_handlers",
)

LOGGER_NAME = "SoAI.mcp.tools.session_config"


async def attach_context_handlers(
    config: ConfigProtocol,
    state: BrowserSessionState,
) -> None:
    resolved_block_images = browser_bool(config, "TOOLS.MCP.BROWSER.BLOCK_IMAGES")
    resolved_block_fonts = browser_bool(config, "TOOLS.MCP.BROWSER.BLOCK_FONTS")
    resolved_block_media = browser_bool(config, "TOOLS.MCP.BROWSER.BLOCK_MEDIA")
    resolved_block_ads = browser_bool(config, "TOOLS.MCP.BROWSER.BLOCK_ADS")
    dns_timeout_sec = resolve_browser_dns_timeout_sec(config)
    route_handler = make_route_handler(
        config,
        state,
        block_images=resolved_block_images,
        block_fonts=resolved_block_fonts,
        block_media=resolved_block_media,
        block_ads=resolved_block_ads,
        dns_timeout_sec=dns_timeout_sec,
        runtime_flags=state.runtime_flags,
    )
    await state.context.route("**/*", route_handler)
    websocket_route_handler = make_websocket_route_handler(
        config,
        dns_timeout_sec=dns_timeout_sec,
        runtime_flags=state.runtime_flags,
    )
    await state.context.route_web_socket("**/*", websocket_route_handler)


def attach_page_handlers(
    config: ConfigProtocol,
    state: BrowserSessionState,
    page: Page,
) -> None:
    logger = get_logger(LOGGER_NAME)
    max_entries = browser_min_int(config, "TOOLS.MCP.BROWSER.LOG_MAX_ENTRIES", 500, min_value=1)

    console_handler = make_console_handler(state)
    page.on("console", console_handler)

    response_handler = make_response_handler(state, max_entries)
    page.on("response", response_handler)

    request_failed_handler = make_request_failed_handler(state)
    page.on("requestfailed", request_failed_handler)

    dialog_handler = make_dialog_handler(state)
    page.on("dialog", dialog_handler)

    download_handler = make_download_handler(state, logger)
    page.on("download", download_handler)

    page_close_handler = make_page_close_handler(state)
    page.on("close", page_close_handler)


def apply_page_timeouts(config: ConfigProtocol, page: Page) -> None:
    nav_timeout_sec = browser_min_int(
        config,
        "TOOLS.MCP.BROWSER.DEFAULT_NAV_TIMEOUT_SEC",
        30,
        min_value=1,
    )
    action_timeout_sec = browser_min_int(
        config,
        "TOOLS.MCP.BROWSER.DEFAULT_ACTION_TIMEOUT_SEC",
        15,
        min_value=1,
    )
    page.set_default_navigation_timeout(nav_timeout_sec * 1000)
    page.set_default_timeout(action_timeout_sec * 1000)

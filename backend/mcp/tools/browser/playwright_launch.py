"""SoAI - Playwright browser launch operations [backend/mcp/tools/browser/playwright_launch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.config.protocols import ConfigProtocol
from core.runtime.websocket_policy import validate_runtime_websocket_url
from mcp.tools.browser.playwright_driver_calls import await_playwright_driver_call
from mcp.tools.browser.playwright_policy import (
    ensure_playwright_browsers_path,
    ensure_playwright_chromium_available,
    require_playwright_chromium_ready,
    resolve_playwright_launch_args,
    should_retry_playwright_auto_install_after_launch_error,
)
from mcp.tools.browser.playwright_runtime_options import PlaywrightRuntimeOptions

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright

    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONValue

__all__ = (
    "ensure_chromium_available_for_launch",
    "launch_local_chromium_browser",
    "launch_playwright_browser",
    "require_chromium_ready_for_launch",
)

_OPERATION_BROWSER_LAUNCH = "mcp.browser.playwright_launch.browser"
_OPERATION_CDP_CONNECT = "mcp.browser.playwright_launch.cdp_connect"


async def require_chromium_ready_for_launch(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    install_lock: asyncio.Lock | None,
) -> None:
    ensure_playwright_browsers_path()
    if install_lock is None:
        await require_playwright_chromium_ready(config, runtime_flags)
        return
    async with install_lock:
        await require_playwright_chromium_ready(config, runtime_flags)


async def ensure_chromium_available_for_launch(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    install_lock: asyncio.Lock | None,
) -> None:
    if install_lock is None:
        await ensure_playwright_chromium_available(config, runtime_flags, force=True)
        return
    async with install_lock:
        await ensure_playwright_chromium_available(config, runtime_flags, force=True)


async def launch_local_chromium_browser(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    playwright: Playwright,
    headless: bool,
    install_lock: asyncio.Lock | None,
    logger: LoggerProtocol,
    channel: str | None = None,
    operation: str = _OPERATION_BROWSER_LAUNCH,
) -> Browser:
    launch_args = resolve_playwright_launch_args()
    details: Mapping[str, JSONValue] = {
        "browser": "chromium",
        "headless": bool(headless),
        "channel": channel,
    }
    try:
        if channel is None:
            await require_chromium_ready_for_launch(
                config,
                runtime_flags,
                install_lock=install_lock,
            )
        return await await_playwright_driver_call(
            playwright.chromium.launch(
                headless=bool(headless),
                channel=channel,
                args=launch_args,
            ),
            operation=operation,
            logger=logger,
            details=details,
            failure_message="Playwright browser launch failed because the driver connection closed.",
        )
    except Error as exception:
        if channel is None and should_retry_playwright_auto_install_after_launch_error(
            config,
            runtime_flags,
            exception,
        ):
            await ensure_chromium_available_for_launch(
                config,
                runtime_flags,
                install_lock=install_lock,
            )
            return await await_playwright_driver_call(
                playwright.chromium.launch(
                    headless=bool(headless),
                    channel=channel,
                    args=launch_args,
                ),
                operation=operation,
                logger=logger,
                details=details,
                failure_message="Playwright browser launch failed because the driver connection closed.",
            )
        raise


async def launch_playwright_browser(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    playwright: Playwright,
    runtime_options: PlaywrightRuntimeOptions,
    install_lock: asyncio.Lock | None,
    logger: LoggerProtocol,
) -> Browser:
    cdp_url = runtime_options.cdp_url
    if cdp_url is None:
        return await launch_local_chromium_browser(
            config=config,
            runtime_flags=runtime_flags,
            playwright=playwright,
            headless=runtime_options.headless,
            channel=runtime_options.channel,
            install_lock=install_lock,
            logger=logger,
        )
    await validate_runtime_websocket_url(
        runtime_flags,
        cdp_url,
        block_private_networks=False,
        source="MCP browser CDP connection",
    )
    return await await_playwright_driver_call(
        playwright.chromium.connect_over_cdp(
            cdp_url,
            timeout=runtime_options.cdp_connect_timeout_ms,
        ),
        operation=_OPERATION_CDP_CONNECT,
        logger=logger,
        details={"cdp_url": cdp_url},
        failure_message="Playwright CDP connection failed because the driver connection closed.",
    )

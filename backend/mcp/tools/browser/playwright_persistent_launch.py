"""SoAI - Playwright persistent context launch [backend/mcp/tools/browser/playwright_persistent_launch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from playwright.async_api import Error

from core.config.protocols import ConfigProtocol
from mcp.tools.browser.playwright_driver_calls import await_playwright_driver_call
from mcp.tools.browser.playwright_launch import (
    ensure_chromium_available_for_launch,
    require_chromium_ready_for_launch,
)
from mcp.tools.browser.playwright_policy import (
    resolve_playwright_launch_args,
    should_retry_playwright_auto_install_after_launch_error,
)
from mcp.tools.browser.playwright_runtime_options import PlaywrightRuntimeOptions

if TYPE_CHECKING:
    from playwright.async_api import (
        BrowserContext,
        HttpCredentials,
        Playwright,
        ViewportSize,
    )

    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONValue

__all__ = (
    "PlaywrightPersistentContextLaunchOptions",
    "launch_playwright_persistent_context",
)

_OPERATION_PERSISTENT_CONTEXT_LAUNCH = "mcp.browser.playwright_launch.persistent_context"
_BROWSER_SERVICE_WORKERS_POLICY: Literal["block"] = "block"


@dataclass(frozen=True, slots=True)
class PlaywrightPersistentContextLaunchOptions:
    user_data_dir: str
    http_credentials: HttpCredentials | None
    ignore_https_errors: bool
    locale: str | None
    timezone_id: str | None
    extra_http_headers: dict[str, str] | None
    viewport: ViewportSize | None
    device_scale_factor: float | None


async def _launch_chromium_persistent_context(
    *,
    playwright: Playwright,
    runtime_options: PlaywrightRuntimeOptions,
    launch_options: PlaywrightPersistentContextLaunchOptions,
    launch_args: list[str],
    logger: LoggerProtocol,
    details: Mapping[str, JSONValue],
) -> BrowserContext:
    return await await_playwright_driver_call(
        playwright.chromium.launch_persistent_context(
            launch_options.user_data_dir,
            headless=runtime_options.headless,
            channel=runtime_options.channel,
            args=launch_args,
            accept_downloads=True,
            service_workers=_BROWSER_SERVICE_WORKERS_POLICY,
            http_credentials=launch_options.http_credentials,
            ignore_https_errors=bool(launch_options.ignore_https_errors),
            locale=launch_options.locale,
            timezone_id=launch_options.timezone_id,
            extra_http_headers=launch_options.extra_http_headers,
            viewport=launch_options.viewport,
            device_scale_factor=launch_options.device_scale_factor,
        ),
        operation=_OPERATION_PERSISTENT_CONTEXT_LAUNCH,
        logger=logger,
        details=details,
        failure_message="Playwright persistent context launch failed because the driver connection closed.",
    )


async def launch_playwright_persistent_context(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    playwright: Playwright,
    runtime_options: PlaywrightRuntimeOptions,
    launch_options: PlaywrightPersistentContextLaunchOptions,
    install_lock: asyncio.Lock | None,
    logger: LoggerProtocol,
) -> BrowserContext:
    launch_args = resolve_playwright_launch_args()
    details: Mapping[str, JSONValue] = {
        "browser": "chromium",
        "headless": runtime_options.headless,
        "channel": runtime_options.channel,
        "user_data_dir": launch_options.user_data_dir,
    }
    try:
        if runtime_options.channel is None:
            await require_chromium_ready_for_launch(
                config,
                runtime_flags,
                install_lock=install_lock,
            )
        return await _launch_chromium_persistent_context(
            playwright=playwright,
            runtime_options=runtime_options,
            launch_options=launch_options,
            launch_args=launch_args,
            logger=logger,
            details=details,
        )
    except Error as exception:
        if (
            runtime_options.channel is None
            and should_retry_playwright_auto_install_after_launch_error(
                config,
                runtime_flags,
                exception,
            )
        ):
            await ensure_chromium_available_for_launch(
                config,
                runtime_flags,
                install_lock=install_lock,
            )
            return await _launch_chromium_persistent_context(
                playwright=playwright,
                runtime_options=runtime_options,
                launch_options=launch_options,
                launch_args=launch_args,
                logger=logger,
                details=details,
            )
        raise

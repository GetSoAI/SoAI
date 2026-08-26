"""SoAI - Playwright runtime for MCP browser tools [backend/mcp/tools/browser/playwright_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from playwright.async_api import HttpCredentials, async_playwright

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from mcp.tools.browser.playwright_driver_calls import await_playwright_driver_call
from mcp.tools.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
)
from mcp.tools.browser.playwright_launch import (
    launch_playwright_browser,
)
from mcp.tools.browser.playwright_persistent_launch import (
    PlaywrightPersistentContextLaunchOptions,
    launch_playwright_persistent_context,
)
from mcp.tools.browser.playwright_policy import ensure_playwright_browsers_path
from mcp.tools.browser.playwright_runtime_cleanup import (
    cleanup_disconnected_playwright_driver,
    shutdown_playwright_runtime,
)
from mcp.tools.browser.playwright_runtime_options import (
    resolve_playwright_runtime_options,
)
from mcp.tools.browser.playwright_runtime_shutdown import (
    close_browser_context_with_logging,
    close_browser_with_logging,
    stop_playwright_with_logging,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Playwright, ViewportSize

    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("PlaywrightBrowserRuntime",)

LOGGER_NAME = "SoAI.mcp.tools.playwright_runtime"
_OPERATION_START_PLAYWRIGHT = "mcp.browser.playwright_runtime.start"


class PlaywrightBrowserRuntime:
    def __init__(
        self,
        *,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        driver_disconnect_notifier: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        if config is None:
            raise ValidationError("Config is required for PlaywrightBrowserRuntime.")
        if runtime_flags is None:
            raise ValidationError("runtime_flags is required for PlaywrightBrowserRuntime.")
        self._config = config
        self._runtime_flags = runtime_flags
        self._state_lock = asyncio.Lock()
        self._playwright_start_lock = asyncio.Lock()
        self._driver_lifecycle_lock = asyncio.Lock()
        self._install_lock = asyncio.Lock()
        self._runtime_locks: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=3600.0,
                max_size=512,
                cleanup_interval_seconds=300.0,
            ),
        )
        self._playwright: Playwright | None = None
        self._browsers: dict[str, Browser] = {}
        self._shutting_down = False
        self._driver_disconnect_notifier = driver_disconnect_notifier

    async def _ensure_playwright_started(self) -> Playwright:
        async with self._state_lock:
            if self._playwright is not None:
                return self._playwright
            if self._shutting_down:
                raise StateError("Playwright runtime is shutting down.")
        async with self._playwright_start_lock:
            async with self._state_lock:
                if self._playwright is not None:
                    return self._playwright
                if self._shutting_down:
                    raise StateError("Playwright runtime is shutting down.")
            ensure_playwright_browsers_path()
            playwright_manager = async_playwright()
            playwright = await await_playwright_driver_call(
                playwright_manager.start(),
                operation=_OPERATION_START_PLAYWRIGHT,
                logger=get_logger(LOGGER_NAME),
                details={"driver": "playwright"},
                failure_message="Playwright driver start failed because the driver connection closed.",
            )
            async with self._state_lock:
                if self._shutting_down:
                    self._playwright = None
                else:
                    self._playwright = playwright
                    return playwright
            await stop_playwright_with_logging(playwright, logger=get_logger(LOGGER_NAME))
            raise StateError("Playwright runtime is shutting down.")

    async def _get_cached_browser(self, runtime_key: str) -> Browser | None:
        async with self._state_lock:
            if self._shutting_down:
                raise StateError("Playwright runtime is shutting down.")
            cached = self._browsers.get(runtime_key)
            if cached is not None and cached.is_connected():
                return cached
            if cached is not None:
                self._browsers.pop(runtime_key, None)
            return None

    async def _store_browser(self, runtime_key: str, browser: Browser) -> Browser:
        async with self._state_lock:
            if self._shutting_down:
                raise StateError("Playwright runtime is shutting down.")
            self._browsers[runtime_key] = browser
            return browser

    async def ensure_browser(self, *, profile: str) -> Browser:
        runtime_options = resolve_playwright_runtime_options(self._config, profile=profile)
        runtime_key = runtime_options.runtime_key
        async with self._runtime_locks.lock(runtime_key):
            async with self._driver_lifecycle_lock:
                cached = await self._get_cached_browser(runtime_key)
                if cached is not None:
                    return cached
                playwright = await self._ensure_playwright_started()
                try:
                    browser = await launch_playwright_browser(
                        config=self._config,
                        runtime_flags=self._runtime_flags,
                        playwright=playwright,
                        runtime_options=runtime_options,
                        install_lock=self._install_lock,
                        logger=get_logger(LOGGER_NAME),
                    )
                except PlaywrightDriverConnectionClosedError:
                    async with self._state_lock:
                        if self._playwright is not playwright:
                            raise
                        browsers = list(self._browsers.values())
                        self._browsers = {}
                        self._playwright = None
                    await cleanup_disconnected_playwright_driver(
                        playwright=playwright,
                        browsers=browsers,
                        logger=get_logger(LOGGER_NAME),
                        notifier=self._driver_disconnect_notifier,
                    )
                    raise
                try:
                    return await self._store_browser(runtime_key, browser)
                except StateError:
                    await close_browser_with_logging(browser, logger=get_logger(LOGGER_NAME))
                    raise

    async def launch_persistent_context(
        self,
        *,
        profile: str,
        user_data_dir: str,
        http_credentials: HttpCredentials | None = None,
        ignore_https_errors: bool = False,
        locale: str | None = None,
        timezone_id: str | None = None,
        extra_http_headers: dict[str, str] | None = None,
        viewport: ViewportSize | None = None,
        device_scale_factor: float | None = None,
    ) -> BrowserContext:
        runtime_options = resolve_playwright_runtime_options(self._config, profile=profile)
        if runtime_options.cdp_url is not None:
            raise ValidationError(
                "Persistent user-data-dir profiles are not supported for remote CDP browser profiles.",
            )
        runtime_key = f"persistent:{profile}:{user_data_dir}"
        async with self._runtime_locks.lock(runtime_key):
            async with self._driver_lifecycle_lock:
                playwright = await self._ensure_playwright_started()
                try:
                    context = await launch_playwright_persistent_context(
                        config=self._config,
                        runtime_flags=self._runtime_flags,
                        playwright=playwright,
                        runtime_options=runtime_options,
                        launch_options=PlaywrightPersistentContextLaunchOptions(
                            user_data_dir=user_data_dir,
                            http_credentials=http_credentials,
                            ignore_https_errors=bool(ignore_https_errors),
                            locale=locale,
                            timezone_id=timezone_id,
                            extra_http_headers=extra_http_headers,
                            viewport=viewport,
                            device_scale_factor=device_scale_factor,
                        ),
                        install_lock=self._install_lock,
                        logger=get_logger(LOGGER_NAME),
                    )
                    async with self._state_lock:
                        if not self._shutting_down:
                            return context
                    await close_browser_context_with_logging(
                        context,
                        logger=get_logger(LOGGER_NAME),
                    )
                    raise StateError("Playwright runtime is shutting down.")
                except PlaywrightDriverConnectionClosedError:
                    async with self._state_lock:
                        if self._playwright is not playwright:
                            raise
                        browsers = list(self._browsers.values())
                        self._browsers = {}
                        self._playwright = None
                    await cleanup_disconnected_playwright_driver(
                        playwright=playwright,
                        browsers=browsers,
                        logger=get_logger(LOGGER_NAME),
                        notifier=self._driver_disconnect_notifier,
                    )
                    raise

    async def shutdown(self) -> None:
        async with self._driver_lifecycle_lock:
            async with self._state_lock:
                self._shutting_down = True
                browsers = list(self._browsers.values())
                playwright = self._playwright
                self._browsers = {}
                self._playwright = None
            await shutdown_playwright_runtime(
                playwright=playwright,
                browsers=browsers,
                logger=get_logger(LOGGER_NAME),
            )

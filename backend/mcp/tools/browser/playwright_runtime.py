"""SoAI - Playwright runtime for MCP browser tools [backend/mcp/tools/browser/playwright_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from playwright.async_api import HttpCredentials

from core.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
)
from core.browser.playwright_lifecycle import (
    PlaywrightDriverSession,
    acquire_playwright_session,
    start_playwright_session,
)
from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError, ValidationError
from core.logging.trace import get_logger
from mcp.tools.browser.playwright_driver_calls import await_playwright_driver_call
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
        driver_disconnect_notifier: Callable[[int], Awaitable[None]] | None = None,
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
        self._playwright_session: PlaywrightDriverSession | None = None
        self._driver_generation = 0
        self._browsers: dict[str, Browser] = {}
        self._shutting_down = False
        self._driver_disconnect_notifier = driver_disconnect_notifier

    async def _ensure_playwright_started(self) -> Playwright:
        async with self._playwright_start_lock:
            async with self._state_lock:
                if self._shutting_down:
                    raise StateError("Playwright runtime is shutting down.")
                session = self._playwright_session
                if session is not None and session.is_active:
                    return session.playwright
                generation = self._driver_generation
            if session is not None:
                await self._invalidate_driver_locked(
                    generation,
                    PlaywrightDriverConnectionClosedError("Playwright driver is no longer active."),
                )
            ensure_playwright_browsers_path()
            async with self._state_lock:
                if self._shutting_down:
                    raise StateError("Playwright runtime is shutting down.")
                session = acquire_playwright_session()
                self._playwright_session = session
                self._driver_generation += 1
            try:
                await await_playwright_driver_call(
                    start_playwright_session(session),
                    operation=_OPERATION_START_PLAYWRIGHT,
                    logger=get_logger(LOGGER_NAME),
                    details={"driver": "playwright"},
                    failure_message="Playwright driver start failed because the driver connection closed.",
                )
                async with self._state_lock:
                    if not self._shutting_down:
                        return session.playwright
                await stop_playwright_with_logging(session, logger=get_logger(LOGGER_NAME))
                raise StateError("Playwright runtime is shutting down.")

            finally:
                async with self._state_lock:
                    if self._playwright_session is session and session.resources_closed:
                        self._playwright_session = None

    async def _get_cached_browser(self, runtime_key: str) -> Browser | None:
        async with self._state_lock:
            if self._shutting_down:
                raise StateError("Playwright runtime is shutting down.")
            if self._playwright_session is None or not self._playwright_session.is_active:
                return None
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

    async def generation_for_browser(self, browser: Browser) -> int:
        async with self._state_lock:
            if (
                self._playwright_session is None
                or not self._playwright_session.is_active
                or not any(cached is browser for cached in self._browsers.values())
            ):
                raise StateError("Playwright browser belongs to an inactive driver.")
            return self._driver_generation

    def _is_generation_active_locked(self, generation: int) -> bool:
        return (
            not self._shutting_down
            and self._playwright_session is not None
            and self._playwright_session.is_active
            and self._driver_generation == generation
        )

    async def is_generation_active(self, generation: int) -> bool:
        async with self._state_lock:
            return self._is_generation_active_locked(generation)

    @asynccontextmanager
    async def active_generation(self, generation: int) -> AsyncGenerator[None]:
        async with self._state_lock:
            if not self._is_generation_active_locked(generation):
                raise StateError("Playwright driver changed during browser session creation.")
            yield

    async def _invalidate_driver_locked(
        self,
        generation: int,
        primary_exception: PlaywrightDriverConnectionClosedError,
    ) -> None:
        async with self._state_lock:
            if self._playwright_session is None or self._driver_generation != generation:
                return
            playwright = self._playwright_session
            browsers = list(self._browsers.values())
            self._browsers = {}
        try:
            notifier = self._driver_disconnect_notifier
            await cleanup_disconnected_playwright_driver(
                playwright=playwright,
                browsers=browsers,
                logger=get_logger(LOGGER_NAME),
                notifier=(lambda: notifier(generation)) if notifier is not None else None,
                primary_exception=primary_exception,
            )
        finally:
            async with self._state_lock:
                if self._playwright_session is playwright and playwright.resources_closed:
                    self._playwright_session = None

    async def handle_driver_disconnect(
        self,
        generation: int,
        exception: PlaywrightDriverConnectionClosedError,
    ) -> None:
        async with self._driver_lifecycle_lock:
            await self._invalidate_driver_locked(generation, exception)

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
                except PlaywrightDriverConnectionClosedError as exception:
                    await self._invalidate_driver_locked(
                        self._driver_generation,
                        exception,
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
    ) -> tuple[BrowserContext, int]:
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
                        if (
                            not self._shutting_down
                            and self._playwright_session is not None
                            and self._playwright_session.playwright is playwright
                        ):
                            return context, self._driver_generation
                    await close_browser_context_with_logging(
                        context,
                        logger=get_logger(LOGGER_NAME),
                    )
                    raise StateError("Playwright runtime is shutting down.")
                except PlaywrightDriverConnectionClosedError as exception:
                    await self._invalidate_driver_locked(
                        self._driver_generation,
                        exception,
                    )
                    raise

    async def shutdown(self) -> None:
        async with self._driver_lifecycle_lock:
            async with self._state_lock:
                self._shutting_down = True
                browsers = list(self._browsers.values())
                playwright = self._playwright_session
                self._browsers = {}
            try:
                await shutdown_playwright_runtime(
                    playwright=playwright,
                    browsers=browsers,
                    logger=get_logger(LOGGER_NAME),
                )
            finally:
                async with self._state_lock:
                    if self._playwright_session is playwright and (
                        playwright is None or playwright.resources_closed
                    ):
                        self._playwright_session = None

    @property
    def resources_closed(self) -> bool:
        return self._playwright_session is None and not self._browsers

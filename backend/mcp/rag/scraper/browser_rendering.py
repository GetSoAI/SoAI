"""SoAI - Playwright-based browser rendering for web scraping [backend/mcp/rag/scraper/browser_rendering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from playwright.async_api import Error, async_playwright

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.config.protocols import ConfigProtocol
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.browser_policy_error_text import (
    normalize_browser_policy_error_message,
)
from core.network.policy import enforce_url_network_policy
from core.runtime.network_policy import (
    OfflineModeError,
    enforce_offline_policy,
    is_offline_mode_enabled,
)
from core.runtime.protocols import RuntimeFlagsViewProtocol
from mcp.tools.browser.playwright_launch import (
    launch_local_chromium_browser,
)
from mcp.tools.browser.playwright_runtime_shutdown import (
    close_browser_context_with_logging,
    close_browser_with_logging,
)
from mcp.tools.browser.request_routing import (
    evaluate_request_routing_for_playwright_request,
)

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Request, Route

    from core.logging.protocols import LoggerProtocol

__all__ = (
    "RenderedPage",
    "render_url_to_html",
)

LOGGER_NAME = "SoAI.mcp.rag.browser_rendering"
OPERATION = "mcp.rag.scraper.browser_render.route"
OPERATION_LAUNCH = "mcp.rag.scraper.browser_render.launch"
OPERATION_CLOSE_CONTEXT = "mcp.rag.scraper.browser_render.close_context"
OPERATION_CLOSE_BROWSER = "mcp.rag.scraper.browser_render.close_browser"
BROWSER_RENDER_CLOSE_EXCEPTIONS: tuple[type[Exception], ...] = (
    Error,
    *RECOVERABLE_EXCEPTIONS,
)


@dataclass(frozen=True, slots=True)
class RenderedPage:
    html: str
    title: str
    final_url: str


async def _close_render_browser_resources(
    *,
    logger: LoggerProtocol,
    context: BrowserContext | None,
    browser: Browser | None,
) -> None:
    primary_exception: Exception | None = None
    try:
        if context is not None:
            await close_browser_context_with_logging(context, logger=logger)
    except BROWSER_RENDER_CLOSE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_CLOSE_CONTEXT,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to close browser render context.",
            operation=OPERATION_CLOSE_CONTEXT,
        )
        primary_exception = exception
    try:
        if browser is not None:
            await close_browser_with_logging(browser, logger=logger)
    except BROWSER_RENDER_CLOSE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_CLOSE_BROWSER,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to close browser render browser.",
            operation=OPERATION_CLOSE_BROWSER,
        )
        if primary_exception is not None:
            raise primary_exception from exception
        raise
    if primary_exception is not None:
        raise primary_exception


async def render_url_to_html(
    runtime_flags: RuntimeFlagsViewProtocol,
    *,
    config: ConfigProtocol,
    adblock_service: EasyListAdblockServiceProtocol | None,
    url: str,
    dns_timeout_sec: float,
    headless: bool,
    nav_timeout_sec: int,
    stabilize_ms: int,
    block_images: bool,
    block_fonts: bool,
    block_media: bool,
    block_ads: bool,
    block_private_networks: bool,
) -> RenderedPage:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    normalized_url = url.strip()
    parsed = urlparse(normalized_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError(f"Only http/https URLs are supported for browser rendering: {url}")
    await enforce_offline_policy(runtime_flags, normalized_url, source="browser render")

    async with async_playwright() as playwright:
        browser: Browser | None = None
        context: BrowserContext | None = None

        browser = await launch_local_chromium_browser(
            config=config,
            runtime_flags=runtime_flags,
            playwright=playwright,
            headless=bool(headless),
            install_lock=None,
            logger=logger,
            operation=OPERATION_LAUNCH,
        )
        try:
            if browser is None:
                raise StateError("Playwright browser launch did not produce a browser instance.")
            context = await browser.new_context()
            host_cache: dict[str, bool] = {}

            async def _route_handler(
                route: Route,
                request: Request,
            ) -> None:
                evaluation = evaluate_request_routing_for_playwright_request(
                    request,
                    block_images=block_images,
                    block_fonts=block_fonts,
                    block_media=block_media,
                    block_ads=block_ads,
                    adblock_service=adblock_service,
                )
                routing_inputs = evaluation.routing_inputs
                request_url = routing_inputs.request_url
                decision = evaluation.decision
                host = ""
                if decision.block:
                    await route.abort()
                    return
                if not isinstance(request_url, str) or not request_url:
                    await route.abort()
                    return
                if not request_url.startswith(("http://", "https://")):
                    await route.continue_()
                    return
                try:
                    await enforce_offline_policy(
                        runtime_flags,
                        request_url,
                        source="browser render request",
                    )
                    host = (urlparse(request_url).hostname or "").lower()
                    cached = host_cache.get(host) if host else None
                    if cached is False:
                        await route.abort()
                        return
                    if not is_offline_mode_enabled(runtime_flags):
                        await asyncio.wait_for(
                            enforce_url_network_policy(
                                request_url,
                                block_private_networks=block_private_networks,
                                dns_timeout_sec=dns_timeout_sec,
                                source="browser render request",
                            ),
                            timeout=max(1.0, float(dns_timeout_sec) + 2.0),
                        )
                    await route.continue_()
                except OfflineModeError:
                    if host:
                        host_cache[host] = False
                    await route.abort()
                except ValidationError as exception:
                    normalized_message = normalize_browser_policy_error_message(str(exception))
                    handled_error = ValidationError(normalized_message)
                    log_handled_exception(
                        logger,
                        handled_error,
                        message="Browser render request blocked due to request policy error (non-critical).",
                        operation=OPERATION,
                        details={"request_url": request_url},
                        level="trace",
                    )
                    if host:
                        host_cache[host] = False
                    await route.abort()
                except RECOVERABLE_EXCEPTIONS as exception:
                    coerced = coerce_to_soai_error(
                        exception,
                        operation="mcp.rag.scraper.browser_render.route",
                    )
                    log_handled_exception(
                        logger,
                        coerced,
                        message="Browser render request blocked due to request policy error (non-critical).",
                        operation=OPERATION,
                        details={"request_url": request_url},
                        level="trace",
                    )
                    if host:
                        host_cache[host] = False
                    await route.abort()

            await context.route("**/*", _route_handler)
            page = await context.new_page()
            page.set_default_navigation_timeout(int(nav_timeout_sec) * 1000)
            await page.goto(normalized_url, wait_until="domcontentloaded")
            if stabilize_ms > 0:
                await page.wait_for_timeout(int(stabilize_ms))
            html = await page.content()
            title = await page.title()
            final_url = page.url or normalized_url
            return RenderedPage(html=html, title=title, final_url=final_url)
        finally:
            await _close_render_browser_resources(
                logger=logger,
                context=context,
                browser=browser,
            )

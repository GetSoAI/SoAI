"""SoAI - WebUI link preview screenshot capturer [backend/app/webui/link_preview_screenshot_capturer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from playwright.async_api import Error

from app.webui.link_preview_screenshot_route_handler import (
    build_link_preview_screenshot_route_handler,
)
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.media_preview.media_preview_settings import MediaPreviewSettings
from core.network.browser_policy_error_text import (
    is_browser_policy_error_message,
    normalize_browser_policy_error_message,
)
from core.network.urls import normalize_http_url
from core.runtime.network_policy import OfflineModeError
from core.web.html_base_href_injection import inject_base_href
from core.webui_manager.protocols import WebUILinkPreviewScreenshotCapturerProtocol
from mcp.tools.browser.blank_page_screenshot_policy import (
    is_solid_color_png,
    should_skip_blank_screenshot,
)
from mcp.tools.browser.config_values import resolve_browser_render_stabilize_ms
from mcp.tools.browser.navigation_validation import build_navigation_url_candidates
from mcp.tools.browser.playwright_error_classification import is_download_starting_error
from mcp.tools.browser.runtime_cache import get_cached_playwright_runtime
from mcp.tools.error import MCPToolError
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "LinkPreviewScreenshotCapturer",
    "LinkPreviewScreenshotCapturerDependencies",
)

LOGGER_NAME = "SoAI.app.webui.link_preview_screenshot_capturer"
OPERATION_CAPTURE = "webui.media.link_preview.screenshot.capture"
OPERATION_CLOSE_CONTEXT = "webui.media.link_preview.screenshot.close_context"
OPERATION_PREVALIDATE_URL = "webui.media.link_preview.screenshot.prevalidate_url"
_CAPTURE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    Error,
    TimeoutError,
    ValidationError,
    *RECOVERABLE_EXCEPTIONS,
)
_CLOSE_EXCEPTIONS: tuple[type[BaseException], ...] = (Error, *RECOVERABLE_EXCEPTIONS)


@dataclass(frozen=True, slots=True)
class LinkPreviewScreenshotCapturerDependencies:
    config: ConfigProtocol
    settings: MediaPreviewSettings
    policy: RemoteMediaPolicy

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LinkPreviewScreenshotCapturerDependencies",
            config=self.config,
            policy=self.policy,
            settings=self.settings,
        )


def _is_browser_enabled(config: ConfigProtocol) -> bool:
    return bool(config.get_bool("TOOLS.MCP.BROWSER.ENABLED"))


class LinkPreviewScreenshotCapturer(WebUILinkPreviewScreenshotCapturerProtocol):
    __slots__ = ("_deps",)

    def __init__(self, deps: LinkPreviewScreenshotCapturerDependencies) -> None:
        self._deps = deps

    @override
    async def capture_link_preview_screenshot_png(
        self,
        runtime_flags: RuntimeFlagsViewProtocol,
        *,
        url: str,
        source_html: str | None = None,
    ) -> tuple[bytes | None, str | None]:
        logger = get_logger(LOGGER_NAME)
        if not _is_browser_enabled(self._deps.config):
            return (None, "Browser tools are disabled; cannot capture screenshot.")
        html = source_html.strip() if isinstance(source_html, str) else ""
        try:
            normalized_url = normalize_http_url(url)
        except ValidationError as exception:
            return (None, str(exception))
        try:
            await self._deps.policy.enforce(
                runtime_flags,
                normalized_url,
                source="WebUI link preview screenshot",
            )
        except OfflineModeError as exception:
            return (None, str(exception))
        except ValidationError as exception:
            normalized_message = normalize_browser_policy_error_message(str(exception))
            handled_error = ValidationError(normalized_message)
            log_handled_exception(
                logger,
                handled_error,
                message="Link preview screenshot URL validation failed.",
                operation=OPERATION_PREVALIDATE_URL,
                details={"url": normalized_url},
                level="warning",
            )
            return (None, normalized_message)
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_PREVALIDATE_URL,
            )
            log_handled_exception(
                logger,
                coerced,
                message="Link preview screenshot URL validation failed.",
                operation=OPERATION_PREVALIDATE_URL,
                details={"url": normalized_url},
                level="warning",
            )
            return (None, project_public_exception(coerced).message)

        timeout_ms = int(max(1.0, float(self._deps.settings.timeout_sec)) * 1000)
        wall_clock_timeout_sec = float(self._deps.settings.timeout_sec) + 15.0
        stabilize_ms = resolve_browser_render_stabilize_ms(self._deps.config)

        runtime = await get_cached_playwright_runtime(self._deps.config, runtime_flags)
        context: BrowserContext | None = None
        try:
            browser: Browser = await runtime.ensure_browser(profile="default")
            async with asyncio.timeout(wall_clock_timeout_sec):
                context = await browser.new_context()
                page: Page = await context.new_page()
                await page.route(
                    "**/*",
                    build_link_preview_screenshot_route_handler(
                        runtime_flags=runtime_flags,
                        policy=self._deps.policy,
                        logger=logger,
                    ),
                )
                page.set_default_timeout(timeout_ms)
                page.set_default_navigation_timeout(timeout_ms)

                if html:
                    html_payload = inject_base_href(html, base_href=normalized_url)
                    await page.set_content(
                        html_payload,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                else:
                    try:
                        target_url, alternative_url = build_navigation_url_candidates(
                            normalized_url,
                        )
                    except (MCPToolError, ValidationError):
                        target_url, alternative_url = (normalized_url, None)
                    try:
                        await page.goto(
                            target_url,
                            wait_until="domcontentloaded",
                            timeout=timeout_ms,
                        )
                    except (Error, TimeoutError) as goto_error:
                        if is_download_starting_error(goto_error):
                            return (
                                None,
                                "Download is starting; screenshot unavailable.",
                            )
                        if alternative_url is not None and alternative_url != target_url:
                            await page.goto(
                                alternative_url,
                                wait_until="domcontentloaded",
                                timeout=timeout_ms,
                            )
                        else:
                            raise
                if stabilize_ms:
                    await page.wait_for_timeout(stabilize_ms)
                if await should_skip_blank_screenshot(
                    page=page,
                    logger=logger,
                    operation=OPERATION_CAPTURE,
                    url=normalized_url,
                ):
                    return (None, "Page rendered blank; screenshot skipped.")
                image_bytes = await page.screenshot(
                    full_page=False,
                    type="png",
                    timeout=timeout_ms,
                )
                if is_solid_color_png(
                    image_bytes_png=image_bytes,
                    logger=logger,
                    operation=OPERATION_CAPTURE,
                    url=normalized_url,
                ):
                    return (None, "Screenshot was a solid color; skipped.")
                return (image_bytes, None)
        except _CAPTURE_EXCEPTIONS as exception:
            error = coerce_to_soai_error(exception, operation=OPERATION_CAPTURE)
            normalized_message = normalize_browser_policy_error_message(error.message)
            if is_browser_policy_error_message(normalized_message):
                handled_error = ValidationError(normalized_message)
                log_handled_exception(
                    logger,
                    handled_error,
                    message="Link preview screenshot capture blocked by browser request policy.",
                    operation=OPERATION_CAPTURE,
                    details={"url": normalized_url},
                    level="warning",
                )
                return (None, normalized_message)
            if isinstance(exception, TimeoutError):
                log_handled_exception(
                    logger,
                    error,
                    message="Link preview screenshot capture timed out.",
                    operation=OPERATION_CAPTURE,
                    details={"url": normalized_url},
                    level="warning",
                )
                return (None, project_public_exception(error).message)
            if isinstance(exception, RECOVERABLE_EXCEPTIONS):
                log_handled_exception(
                    logger,
                    error,
                    message="Link preview screenshot capture failed.",
                    operation=OPERATION_CAPTURE,
                    details={"url": normalized_url},
                    level="warning",
                )
                return (None, project_public_exception(error).message)
            log_exception(
                logger,
                error,
                message="Link preview screenshot capture failed.",
                operation=OPERATION_CAPTURE,
                details={"url": normalized_url},
                level="warning",
            )
            return (None, project_public_exception(error).message)
        finally:
            if context is not None:
                try:
                    await context.close()
                except _CLOSE_EXCEPTIONS as exception:
                    error = coerce_to_soai_error(
                        exception,
                        operation=OPERATION_CLOSE_CONTEXT,
                    )
                    log_handled_exception(
                        logger,
                        error,
                        message="Failed to close link preview screenshot browser context (non-critical).",
                        operation=OPERATION_CLOSE_CONTEXT,
                        level="debug",
                    )

"""SoAI - Web fetch screenshot capture helpers [backend/mcp/handlers/tools/web_fetch_screenshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.browser_policy_error_text import (
    is_browser_policy_error_message,
    normalize_browser_policy_error_message,
)
from core.network.policy import enforce_url_network_policy
from core.runtime.network_policy import OfflineModeError
from core.web.html_base_href_injection import inject_base_href
from mcp.tools.browser.config_values import (
    resolve_browser_default_nav_timeout_sec,
    resolve_browser_render_stabilize_ms,
    resolve_web_fetch_block_private_networks,
    resolve_web_fetch_dns_timeout_sec,
)
from mcp.tools.browser.navigation_capture import capture_navigation_screenshot
from mcp.tools.browser.navigation_validation import build_navigation_url_candidates
from mcp.tools.browser.playwright_error_classification import is_download_starting_error
from mcp.tools.browser.runtime_cache import (
    get_cached_playwright_runtime,
    shutdown_cached_playwright_runtime,
)
from mcp.tools.browser.session_config import apply_page_timeouts, attach_page_handlers
from mcp.tools.browser.types import BrowserSessionState
from mcp.tools.error import MCPToolError
from mcp.tools.offline_policy import (
    is_offline_mode_enabled,
    require_url_allowed_when_offline,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict

__all__ = (
    "capture_web_fetch_screenshot",
    "shutdown_cached_web_fetch_screenshot_runtime",
)

LOGGER_NAME = "SoAI.mcp.handlers.web_fetch_screenshot"
OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE = "mcp.rag.web_fetch_screenshot.capture"
OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CLOSE_CONTEXT = "mcp.rag.web_fetch_screenshot.close_context"
OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_PREVALIDATE_URL = (
    "mcp.rag.web_fetch_screenshot.prevalidate_url"
)
WEB_FETCH_SCREENSHOT_FAILURE_MESSAGE = "Web fetch screenshot capture failed."


async def shutdown_cached_web_fetch_screenshot_runtime() -> None:
    await shutdown_cached_playwright_runtime()


async def capture_web_fetch_screenshot(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    storage_manager: StorageManagerProtocol,
    url: str,
    source_html: str | None = None,
    adblock_service: EasyListAdblockServiceProtocol | None = None,
) -> tuple[JSONDict | None, str | None]:
    logger = get_logger(LOGGER_NAME)
    if not bool(config.get_bool("TOOLS.MCP.BROWSER.ENABLED")):
        return (None, "Browser tools are disabled; cannot capture screenshot.")
    try:
        primary_url, fallback_url = build_navigation_url_candidates(url)
    except (MCPToolError, ValidationError) as exception:
        return (None, str(exception))
    try:
        await require_url_allowed_when_offline(
            runtime_flags,
            tool_name="web_fetch (screenshot)",
            url=primary_url,
            capability="web_fetch screenshot",
        )
        if not is_offline_mode_enabled(runtime_flags):
            await enforce_url_network_policy(
                primary_url,
                block_private_networks=resolve_web_fetch_block_private_networks(config),
                dns_timeout_sec=resolve_web_fetch_dns_timeout_sec(config),
                source="MCP web_fetch screenshot",
            )
    except (OfflineModeError, ValidationError) as exception:
        normalized_message = normalize_browser_policy_error_message(str(exception))
        handled_error = ValidationError(normalized_message)
        log_handled_exception(
            logger,
            handled_error,
            message="Web fetch screenshot URL validation failed.",
            operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_PREVALIDATE_URL,
            level="warning",
        )
        return (None, normalized_message)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_PREVALIDATE_URL,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Web fetch screenshot URL validation failed.",
            operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_PREVALIDATE_URL,
            level="warning",
        )
        return (None, project_public_exception(coerced).message)

    nav_timeout_sec = resolve_browser_default_nav_timeout_sec(config)
    timeout_ms = int(nav_timeout_sec) * 1000
    stabilize_ms = resolve_browser_render_stabilize_ms(config)
    wall_clock_timeout_sec = float(nav_timeout_sec) + 15.0

    runtime = await get_cached_playwright_runtime(config, runtime_flags)
    try:
        browser = await runtime.ensure_browser(profile="default")
        async with asyncio.timeout(wall_clock_timeout_sec):
            context = await browser.new_context()
            try:
                state = BrowserSessionState(
                    owner_key="web_fetch",
                    owner_base="web_fetch",
                    context=context,
                    storage_manager=storage_manager,
                    runtime_flags=runtime_flags,
                    adblock_service=adblock_service,
                )
                page = await context.new_page()
                attach_page_handlers(config, state, page)
                apply_page_timeouts(config, page)
                if isinstance(source_html, str) and source_html.strip():
                    html_payload = inject_base_href(source_html, base_href=str(primary_url))
                    await page.set_content(
                        html_payload,
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                else:
                    try:
                        await page.goto(
                            primary_url,
                            wait_until="domcontentloaded",
                            timeout=timeout_ms,
                        )
                    except (Error, TimeoutError):
                        if fallback_url is None:
                            raise
                        await require_url_allowed_when_offline(
                            runtime_flags,
                            tool_name="web_fetch (screenshot)",
                            url=fallback_url,
                            capability="web_fetch screenshot",
                        )
                        if not is_offline_mode_enabled(runtime_flags):
                            await enforce_url_network_policy(
                                fallback_url,
                                block_private_networks=resolve_web_fetch_block_private_networks(
                                    config,
                                ),
                                dns_timeout_sec=resolve_web_fetch_dns_timeout_sec(config),
                                source="MCP web_fetch screenshot",
                            )
                        await page.goto(
                            fallback_url,
                            wait_until="domcontentloaded",
                            timeout=timeout_ms,
                        )
                if stabilize_ms:
                    await page.wait_for_timeout(stabilize_ms)
                return await capture_navigation_screenshot(
                    page=page,
                    timeout_ms=timeout_ms,
                    operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
                    failure_message=WEB_FETCH_SCREENSHOT_FAILURE_MESSAGE,
                )
            finally:
                try:
                    await context.close()
                except Error as exception:
                    error = coerce_to_soai_error(
                        exception,
                        operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CLOSE_CONTEXT,
                    )
                    log_handled_exception(
                        logger,
                        error,
                        message=(
                            "Failed to close web fetch screenshot browser context (non-critical)."
                        ),
                        operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CLOSE_CONTEXT,
                        level="debug",
                    )
                except RECOVERABLE_EXCEPTIONS as exception:
                    error = coerce_to_soai_error(
                        exception,
                        operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CLOSE_CONTEXT,
                    )
                    log_handled_exception(
                        logger,
                        error,
                        message=(
                            "Failed to close web fetch screenshot browser context (non-critical)."
                        ),
                        operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CLOSE_CONTEXT,
                        level="debug",
                    )
    except (Error, TimeoutError, OfflineModeError, ValidationError) as exception:
        if isinstance(exception, Error) and is_download_starting_error(exception):
            return (
                None,
                f"Download is starting; screenshot unavailable. Use browser_navigate(action='url', url={url!r}) to capture the download, then browser_downloads to obtain file_path.",
            )
        error = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
        )
        normalized_message = normalize_browser_policy_error_message(error.message)
        if is_browser_policy_error_message(normalized_message):
            handled_error = ValidationError(normalized_message)
            log_handled_exception(
                logger,
                handled_error,
                message="Web fetch screenshot capture blocked by browser request policy.",
                operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
                level="warning",
            )
            return (None, normalized_message)
        if isinstance(exception, OfflineModeError):
            log_handled_exception(
                logger,
                error,
                message="Web fetch screenshot capture is blocked by offline mode.",
                operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
                level="warning",
            )
            return (None, project_public_exception(error).message)
        if isinstance(exception, TimeoutError):
            log_handled_exception(
                logger,
                error,
                message="Web fetch screenshot capture timed out.",
                operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
                level="warning",
            )
            return (None, project_public_exception(error).message)
        log_exception(
            logger,
            error,
            message="Web fetch screenshot capture failed.",
            operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
            level="warning",
        )
        return (None, project_public_exception(error).message)
    except RECOVERABLE_EXCEPTIONS as exception:
        error = coerce_to_soai_error(
            exception,
            operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
        )
        log_handled_exception(
            logger,
            error,
            message="Web fetch screenshot capture failed.",
            operation=OPERATION_MCP_RAG_WEB_FETCH_SCREENSHOT_CAPTURE,
            level="warning",
        )
        return (None, project_public_exception(error).message)

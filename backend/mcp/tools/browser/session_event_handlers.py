"""SoAI - Browser session event handler factories [backend/mcp/tools/browser/session_event_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import FeatureDisabledError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.network.browser_policy_error_text import (
    normalize_browser_policy_error_message,
)
from core.runtime.network_policy import is_offline_mode_enabled
from core.validation.integers import is_strict_int
from mcp.tools.browser.download_support import create_pending_download
from mcp.tools.browser.request_routing import (
    evaluate_request_routing_for_playwright_request,
)
from mcp.tools.browser.security_policy import (
    enforce_browser_request_policy,
    enforce_browser_websocket_policy,
)
from mcp.tools.browser.types import (
    BrowserConsoleMessage,
    BrowserDialogDescriptor,
    BrowserSessionState,
)

if TYPE_CHECKING:
    from playwright.async_api import (
        ConsoleMessage,
        Dialog,
        Download,
        Page,
        Request,
        Route,
        WebSocketRoute,
    )

    from core.config.protocols import ConfigProtocol
    from core.logging.protocols import StandardLogger
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "make_console_handler",
    "make_dialog_handler",
    "make_download_handler",
    "make_page_close_handler",
    "make_route_handler",
    "make_websocket_route_handler",
)

LOGGER_NAME = "SoAI.mcp.tools.session_event_handlers"
OPERATION = "mcp.browser.session_routing.route"


def make_route_handler(
    config: ConfigProtocol,
    state: BrowserSessionState,
    block_images: bool,
    block_fonts: bool,
    block_media: bool,
    block_ads: bool,
    dns_timeout_sec: float,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> Callable[[Route, Request], Awaitable[None]]:
    logger = get_logger(LOGGER_NAME)

    async def _route_handler(route: Route, request: Request) -> None:
        evaluation = evaluate_request_routing_for_playwright_request(
            request,
            block_images=block_images,
            block_fonts=block_fonts,
            block_media=block_media,
            block_ads=block_ads,
            adblock_service=state.adblock_service,
        )
        routing_inputs = evaluation.routing_inputs
        request_url = routing_inputs.request_url
        decision = evaluation.decision
        if decision.block:
            await route.abort()
            return
        host = (urlparse(request_url).hostname or "").lower()
        if host and host in state.host_block_cache:
            await route.abort()
            return
        try:
            await asyncio.wait_for(
                enforce_browser_request_policy(
                    config,
                    runtime_flags,
                    url=request_url,
                    source="MCP browser tool request",
                ),
                timeout=max(1.0, dns_timeout_sec + 2.0),
            )
            await route.continue_()
        except (FeatureDisabledError, ValidationError) as exception:
            normalized_message = normalize_browser_policy_error_message(str(exception))
            handled_error = ValidationError(normalized_message)
            log_handled_exception(
                logger,
                handled_error,
                message="Browser request blocked due to request policy error (non-critical).",
                operation=OPERATION,
                details={"request_url": request_url},
                level="trace",
            )
            if host and not is_offline_mode_enabled(runtime_flags):
                state.host_block_cache.add(host)
            await route.abort()
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="mcp.browser.session_routing.route",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Browser request blocked due to request policy error (non-critical).",
                operation=OPERATION,
                details={"request_url": request_url},
                level="trace",
            )
            if host and not is_offline_mode_enabled(runtime_flags):
                state.host_block_cache.add(host)
            await route.abort()

    return _route_handler


def make_websocket_route_handler(
    config: ConfigProtocol,
    dns_timeout_sec: float,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> Callable[[WebSocketRoute], Awaitable[None]]:
    logger = get_logger(LOGGER_NAME)

    async def _websocket_route_handler(route: WebSocketRoute) -> None:
        request_url = str(route.url or "")
        try:
            await asyncio.wait_for(
                enforce_browser_websocket_policy(
                    config,
                    runtime_flags,
                    url=request_url,
                    source="MCP browser WebSocket request",
                ),
                timeout=max(1.0, dns_timeout_sec + 2.0),
            )
            route.connect_to_server()
        except (FeatureDisabledError, ValidationError) as exception:
            normalized_message = normalize_browser_policy_error_message(str(exception))
            handled_error = ValidationError(normalized_message)
            log_handled_exception(
                logger,
                handled_error,
                message="Browser WebSocket blocked due to request policy error (non-critical).",
                operation=OPERATION,
                details={"request_url": request_url},
                level="trace",
            )
            await route.close(code=1008, reason="Blocked by SoAI browser policy.")
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="mcp.browser.session_routing.websocket_route",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Browser WebSocket blocked due to request policy error (non-critical).",
                operation=OPERATION,
                details={"request_url": request_url},
                level="trace",
            )
            await route.close(code=1008, reason="Blocked by SoAI browser policy.")

    return _websocket_route_handler


def make_console_handler(state: BrowserSessionState) -> Callable[[ConsoleMessage], None]:
    def _on_console(msg: ConsoleMessage) -> None:
        location = msg.location
        url_raw = location.get("url")
        url = str(url_raw) if isinstance(url_raw, str) and url_raw.strip() else None
        line_raw = location.get("lineNumber")
        line = int(line_raw) if is_strict_int(line_raw) else None
        column_raw = location.get("columnNumber")
        column = int(column_raw) if is_strict_int(column_raw) else None
        message = BrowserConsoleMessage(
            type=str(msg.type or ""),
            text=str(msg.text or ""),
            url=url,
            line=line,
            column=column,
        )
        _ = put_nowait_with_overwrite(state.console_queue, message, overwrite_attempts=1)

    return _on_console


def make_dialog_handler(
    state: BrowserSessionState,
) -> Callable[[Dialog], None]:
    logger = get_logger(LOGGER_NAME)

    def _on_dialog(dialog: Dialog) -> None:
        dialog_id = f"d{int(state.next_dialog_id)}"
        state.next_dialog_id += 1
        descriptor = BrowserDialogDescriptor(
            dialog_id=dialog_id,
            type=str(dialog.type or ""),
            message=str(dialog.message or ""),
            default_value=str(dialog.default_value or ""),
        )
        try:
            state.dialog_queue.put_nowait((descriptor, dialog))
        except asyncio.QueueFull:
            logger.warning("Dialog queue is full; dropping dialog event: %s", dialog_id)

    return _on_dialog


def make_download_handler(
    state: BrowserSessionState,
    logger: StandardLogger,
) -> Callable[[Download], None]:
    def _on_download(download: Download) -> None:
        pending = create_pending_download(state, download)
        try:
            state.download_queue.put_nowait(pending)
        except asyncio.QueueFull:
            logger.warning("Download queue is full; dropping browser download event.")

    return _on_download


def make_page_close_handler(state: BrowserSessionState) -> Callable[[Page], None]:
    def _on_close(_page: Page) -> None:
        page_value = _page
        _ = put_nowait_with_overwrite(state.page_close_queue, page_value, overwrite_attempts=1)

    return _on_close

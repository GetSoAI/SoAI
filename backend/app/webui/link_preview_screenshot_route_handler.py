"""SoAI - WebUI link preview screenshot request routing [backend/app/webui/link_preview_screenshot_route_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.network.browser_policy_error_text import (
    normalize_browser_policy_error_message,
)
from core.network.urls import normalize_http_url
from core.runtime.network_policy import OfflineModeError
from webui.manager.media_preview_remote_policy import RemoteMediaPolicy

if TYPE_CHECKING:
    from playwright.async_api import Request, Route

    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("build_link_preview_screenshot_route_handler",)

OPERATION_WEBUI_LINK_PREVIEW_SCREENSHOT_ROUTE_HANDLER = (
    "app.webui.link_preview_screenshot_route_handler"
)


def build_link_preview_screenshot_route_handler(
    *,
    runtime_flags: RuntimeFlagsViewProtocol,
    policy: RemoteMediaPolicy,
    logger: LoggerProtocol,
) -> Callable[[Route, Request], Awaitable[None]]:
    host_block_cache: set[str] = set()

    async def _route_handler(route: Route, request: Request) -> None:
        request_url = str(request.url or "")
        host = ""
        resource_type = str(request.resource_type or "").strip().lower()
        if resource_type in {"font", "media"}:
            await route.abort()
            return
        if not request_url.startswith(("http://", "https://")):
            await route.continue_()
            return
        try:
            host = (urlparse(request_url).hostname or "").lower().strip()
            if host and host in host_block_cache:
                await route.abort()
                return
            normalized_url = normalize_http_url(request_url)
            await policy.enforce(
                runtime_flags,
                normalized_url,
                source="WebUI link preview screenshot",
            )
            await route.continue_()
        except (OfflineModeError, ValidationError) as exception:
            normalized_message = normalize_browser_policy_error_message(str(exception))
            handled_error = ValidationError(normalized_message)
            log_handled_exception(
                logger,
                handled_error,
                message="Blocked page resource during link preview screenshot capture (non-critical).",
                operation=OPERATION_WEBUI_LINK_PREVIEW_SCREENSHOT_ROUTE_HANDLER,
                details={"request_url": request_url},
                level="trace",
            )
            if host:
                host_block_cache.add(host)
            await route.abort()
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_WEBUI_LINK_PREVIEW_SCREENSHOT_ROUTE_HANDLER,
            )
            log_handled_exception(
                logger,
                coerced,
                message="Blocked page resource during link preview screenshot capture (non-critical).",
                operation=OPERATION_WEBUI_LINK_PREVIEW_SCREENSHOT_ROUTE_HANDLER,
                details={"request_url": request_url},
                level="trace",
            )
            if host:
                host_block_cache.add(host)
            await route.abort()

    return _route_handler

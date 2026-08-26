"""SoAI - Browser session network event capture [backend/mcp/tools/browser/session_network_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.concurrency.queue_ops import put_nowait_with_overwrite
from mcp.tools.browser.download_support import record_download_size_hint
from mcp.tools.browser.request_routing import resolve_request_routing_inputs
from mcp.tools.browser.types import BrowserNetworkQueuedResponse, BrowserSessionState

if TYPE_CHECKING:
    from playwright.async_api import Request, Response

__all__ = ("make_request_failed_handler", "make_response_handler")


def _queue_network_item(
    state: BrowserSessionState,
    request_item: BrowserNetworkQueuedResponse,
) -> None:
    _ = put_nowait_with_overwrite(state.network_queue, request_item, overwrite_attempts=1)


def make_response_handler(
    state: BrowserSessionState,
    max_entries: int,
) -> Callable[[Response], Awaitable[None]]:
    async def _on_response(response: Response) -> None:
        req = response.request
        routing_inputs = resolve_request_routing_inputs(req)
        record_download_size_hint(
            state,
            url=str(response.url or ""),
            content_length_header=response.headers.get("content-length"),
            max_entries=max_entries,
        )
        body_bytes: bytes | None = None
        resource_type = str(req.resource_type or "")
        normalized_resource_type = resource_type.strip().lower()
        if normalized_resource_type in {"xhr", "fetch", "document"}:
            try:
                body_bytes = await response.body()
            except Error:
                body_bytes = None
        _queue_network_item(
            state,
            BrowserNetworkQueuedResponse(
                body_bytes=body_bytes,
                url=str(response.url or ""),
                method=str(req.method or ""),
                status=int(response.status),
                resource_type=resource_type,
                is_main_frame_document=routing_inputs.is_main_frame_document,
            ),
        )

    return _on_response


def make_request_failed_handler(
    state: BrowserSessionState,
) -> Callable[[Request], Awaitable[None]]:
    async def _on_request_failed(request: Request) -> None:
        failure_text = request.failure
        routing_inputs = resolve_request_routing_inputs(request)
        _queue_network_item(
            state,
            BrowserNetworkQueuedResponse(
                body_bytes=None,
                url=str(request.url or ""),
                method=str(request.method or ""),
                status=None,
                resource_type=str(request.resource_type or ""),
                is_main_frame_document=routing_inputs.is_main_frame_document,
                failure_text=(
                    failure_text.strip()
                    if isinstance(failure_text, str) and failure_text.strip()
                    else None
                ),
            ),
        )

    return _on_request_failed

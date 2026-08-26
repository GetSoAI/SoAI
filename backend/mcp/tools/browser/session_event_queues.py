"""SoAI - Browser session event queue draining [backend/mcp/tools/browser/session_event_queues.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.config.protocols import ConfigProtocol
from core.validation.integers import is_strict_int
from mcp.tools.browser.config_values import browser_bounded_int, browser_min_int
from mcp.tools.browser.download_support import drain_download_queue
from mcp.tools.browser.types import (
    BrowserNetworkQueuedResponse,
    BrowserNetworkRequest,
    BrowserSessionState,
)

__all__ = ("drain_event_queues",)


def _resolve_network_body_max_bytes(config: ConfigProtocol) -> int:
    return browser_bounded_int(
        config,
        "TOOLS.MCP.BROWSER.NETWORK_BODY_MAX_BYTES",
        65_536,
        min_value=1024,
        max_value=262_144,
    )


def _build_network_request(
    config: ConfigProtocol,
    queued: BrowserNetworkQueuedResponse,
) -> BrowserNetworkRequest:
    url = str(queued.url or "")
    method = str(queued.method or "")
    status_value = queued.status
    status = int(status_value) if is_strict_int(status_value) else None
    resource_type = str(queued.resource_type or "")
    failure_text = (
        queued.failure_text.strip()
        if isinstance(queued.failure_text, str) and queued.failure_text.strip()
        else None
    )
    body: str | None = None
    body_truncated: bool | None = None
    if queued.body_bytes is not None:
        max_bytes = _resolve_network_body_max_bytes(config)
        truncated = len(queued.body_bytes) > max_bytes
        sliced = queued.body_bytes[:max_bytes] if truncated else queued.body_bytes
        body = sliced.decode("utf-8", errors="replace")
        body_truncated = bool(truncated)
    return BrowserNetworkRequest(
        url=url,
        method=method,
        status=status,
        resource_type=resource_type,
        body=body,
        body_truncated=body_truncated,
        is_main_frame_document=queued.is_main_frame_document,
        failure_text=failure_text,
    )


def drain_event_queues(
    config: ConfigProtocol,
    state: BrowserSessionState,
    *,
    downloads_dir: str | None,
) -> None:
    max_entries = browser_min_int(config, "TOOLS.MCP.BROWSER.LOG_MAX_ENTRIES", 500, min_value=1)
    while True:
        try:
            message = state.console_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        state.console_messages.append(message)
    if len(state.console_messages) > max_entries:
        overflow = len(state.console_messages) - max_entries
        state.console_messages = state.console_messages[overflow:]
        state.console_last_call_index = max(0, state.console_last_call_index - overflow)
        state.console_page_load_index = max(0, state.console_page_load_index - overflow)

    while True:
        try:
            queued_response = state.network_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if not isinstance(queued_response, BrowserNetworkQueuedResponse):
            continue
        request = _build_network_request(config, queued_response)
        state.network_requests.append(request)
    if len(state.network_requests) > max_entries:
        overflow = len(state.network_requests) - max_entries
        state.network_requests = state.network_requests[overflow:]
        state.network_last_call_index = max(0, state.network_last_call_index - overflow)
        state.network_page_load_index = max(0, state.network_page_load_index - overflow)

    while True:
        try:
            descriptor, dialog = state.dialog_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        state.dialogs.append(descriptor)
        state.dialog_objects[descriptor.dialog_id] = dialog

    drain_download_queue(
        config,
        state,
        downloads_dir=downloads_dir,
    )

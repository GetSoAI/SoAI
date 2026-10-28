"""SoAI - Browser session network event capture [backend/mcp/tools/browser/session_network_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
    classify_playwright_driver_connection_closed_exception,
)
from core.concurrency.cancellation_cleanup import (
    current_task_has_pending_cancellation,
    wait_for_task_completion,
)
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError
from core.logging.trace import get_logger
from core.timing.constants import BACKGROUND_TIMEOUT_SEC
from mcp.tools.browser.download_support import record_download_size_hint
from mcp.tools.browser.request_routing import resolve_request_routing_inputs
from mcp.tools.browser.session_state import mark_browser_session_driver_disconnected
from mcp.tools.browser.types import BrowserNetworkQueuedResponse, BrowserSessionState

if TYPE_CHECKING:
    from playwright.async_api import Request, Response

__all__ = ("make_request_failed_handler", "make_response_handler")

LOGGER_NAME = "SoAI.mcp.tools.session_network_events"
OPERATION_RESPONSE = "mcp.browser.session_network_events.response"


def _queue_network_item(
    state: BrowserSessionState,
    request_item: BrowserNetworkQueuedResponse,
) -> None:
    _ = put_nowait_with_overwrite(state.network_queue, request_item, overwrite_attempts=1)


def make_response_handler(
    state: BrowserSessionState,
    max_entries: int,
) -> Callable[[Response], Awaitable[None]]:
    async def _capture_response(response: Response) -> None:
        request = response.request
        routing_inputs = resolve_request_routing_inputs(request)
        record_download_size_hint(
            state,
            url=str(response.url or ""),
            content_length_header=response.headers.get("content-length"),
            max_entries=max_entries,
        )
        body_bytes: bytes | None = None
        driver_error: PlaywrightDriverConnectionClosedError | None = None
        body_capture_cancelled = False
        resource_type = str(request.resource_type or "")
        try:
            if resource_type.strip().lower() in {"xhr", "fetch", "document"}:
                body_bytes = await response.body()
                if current_task_has_pending_cancellation():
                    raise asyncio.CancelledError
        except asyncio.CancelledError:
            body_capture_cancelled = True
            raise
        except Error as exception:
            driver_error = classify_playwright_driver_connection_closed_exception(
                exception, operation=OPERATION_RESPONSE, details={"owner_key": state.owner_key}
            )
        finally:
            primary_exception = sys.exception()
            if isinstance(primary_exception, Exception):
                driver_error = classify_playwright_driver_connection_closed_exception(
                    primary_exception,
                    operation=OPERATION_RESPONSE,
                    details={"owner_key": state.owner_key},
                )
            if not body_capture_cancelled:
                _queue_network_item(
                    state,
                    BrowserNetworkQueuedResponse(
                        body_bytes=body_bytes,
                        url=str(response.url or ""),
                        method=str(request.method or ""),
                        status=int(response.status),
                        resource_type=resource_type,
                        is_main_frame_document=routing_inputs.is_main_frame_document,
                    ),
                )
            if driver_error is not None:
                mark_browser_session_driver_disconnected(state, reason=str(driver_error))
                if (
                    state.driver_disconnect_handler is not None
                    and state.driver_generation is not None
                ):
                    await state.driver_disconnect_handler(state.driver_generation, driver_error)

    async def _on_response(response: Response) -> None:
        capture_task = create_ephemeral_task(
            _capture_response(response), name=OPERATION_RESPONSE, log_exceptions=False
        )
        timeout_failure: SoAITimeoutError | None = None
        try:
            done, _pending = await asyncio.wait({capture_task}, timeout=BACKGROUND_TIMEOUT_SEC)
            if not done:
                timeout_failure = SoAITimeoutError(
                    "Browser response body capture exceeded its deadline.",
                    operation=OPERATION_RESPONSE,
                )
        finally:
            if not capture_task.done():
                capture_task.cancel()
            await wait_for_task_completion(capture_task, retain_resources_until_complete=True)
            failure = None if capture_task.cancelled() else capture_task.exception()
            if failure is None:
                failure = timeout_failure
            if isinstance(failure, Exception):
                driver_error = classify_playwright_driver_connection_closed_exception(
                    failure, operation=OPERATION_RESPONSE, details={"owner_key": state.owner_key}
                )
                if driver_error is None:
                    log_exception(
                        get_logger(LOGGER_NAME),
                        coerce_to_soai_error(failure, operation=OPERATION_RESPONSE),
                        message="Browser response capture failed.",
                        operation=OPERATION_RESPONSE,
                        level="warning" if failure is timeout_failure else "error",
                    )
            elif isinstance(failure, BaseException):
                raise failure
        if capture_task.cancelled() and timeout_failure is None:
            raise asyncio.CancelledError

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

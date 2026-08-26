"""SoAI - Readback of HTTP error responses during execution failures [backend/orchestrator/execution/execution_http_response_readback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exception_logging import log_handled_exception

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("drain_httpx_error_response_body",)

OPERATION = "orchestrator.execution.drain_httpx_error_response_body"


async def drain_httpx_error_response_body(
    exception: httpx2.HTTPStatusError,
    *,
    logger: LoggerProtocol,
) -> None:
    response = exception.response
    if response is None or response.is_closed:
        return
    try:
        await response.aread()
    except (
        httpx2.StreamClosed,
        httpx2.ResponseNotRead,
        OSError,
        RuntimeError,
    ) as read_exception:
        log_handled_exception(
            logger,
            read_exception,
            message="Failed to read response body in execution failure handler.",
            operation=OPERATION,
            level="debug",
        )

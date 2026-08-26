"""SoAI - MCP web fetch execution helpers [backend/mcp/handlers/tools/web_fetch_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

import httpx2

from core.errors.exceptions import ValidationError
from mcp.handlers.tools.web_fetch_errors import raise_web_fetch_failure

__all__ = ("await_web_fetch_operation",)


async def await_web_fetch_operation[ResultT](
    operation: Awaitable[ResultT],
    *,
    timeout_ms: int | None,
    url: str,
) -> ResultT:
    try:
        if timeout_ms is None:
            return await operation
        async with asyncio.timeout(max(0.1, float(timeout_ms) / 1000.0)):
            return await operation
    except (
        httpx2.HTTPStatusError,
        httpx2.RequestError,
        TimeoutError,
        ValidationError,
    ) as exception:
        raise_web_fetch_failure(url, exception)

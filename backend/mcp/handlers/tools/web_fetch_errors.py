"""SoAI - Shared MCP web fetch error translation [backend/mcp/handlers/tools/web_fetch_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

import httpx2

from core.errors.exceptions import ValidationError
from mcp.protocol.types import MCPJSONRPCError

__all__ = ("raise_web_fetch_failure",)


def raise_web_fetch_failure(url: str, exception: Exception) -> NoReturn:
    shared_suffix = (
        "If the page is blocked, JS-rendered, or requires login, use browser_navigate + "
        "browser_snapshot/browser_eval."
    )
    if isinstance(exception, httpx2.HTTPStatusError):
        status_code = exception.response.status_code if exception.response is not None else None
        raise MCPJSONRPCError(
            -32603,
            f"HTTP fetch failed (status={status_code}) for {url}. {shared_suffix}",
        ) from exception
    if isinstance(exception, httpx2.RequestError):
        raise MCPJSONRPCError(
            -32603,
            f"HTTP fetch network error for {url}: {type(exception).__name__}. {shared_suffix}",
        ) from exception
    if isinstance(exception, TimeoutError):
        raise MCPJSONRPCError(
            -32603,
            f"HTTP fetch timed out for {url}. {shared_suffix}",
        ) from exception
    if isinstance(exception, ValidationError):
        raise MCPJSONRPCError(
            -32603,
            f"HTTP fetch failed for {url}: {exception}. {shared_suffix}",
        ) from exception
    raise exception

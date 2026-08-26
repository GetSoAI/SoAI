"""SoAI - MCP provider HTTP response reading [backend/mcp/tools/provider_http.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict
from mcp.tools.error import MCPToolError
from mcp.tools.http_request_response_payload import read_response_body_with_limit
from mcp.tools.http_request_retries import read_retry_after_header

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "build_provider_http_status_message",
    "map_provider_http_exception",
    "parse_provider_json_dict",
    "read_provider_response_bytes",
)


def build_provider_http_status_message(
    status_code: int,
    *,
    provider_label: str,
    auth_rejected_message: str | None = None,
    payment_required_message: str | None = None,
    not_found_message: str | None = None,
    timeout_message: str | None = None,
    rate_limit_message: str,
    unavailable_message: str,
) -> str:
    if status_code in {401, 403} and auth_rejected_message is not None:
        return auth_rejected_message
    if status_code == 402 and payment_required_message is not None:
        return payment_required_message
    if status_code == 404 and not_found_message is not None:
        return not_found_message
    if status_code == 408 and timeout_message is not None:
        return timeout_message
    if status_code == 429:
        return rate_limit_message
    if status_code >= 500:
        return unavailable_message
    return f"{provider_label} returned HTTP {status_code}."


def map_provider_http_exception(
    exception: httpx2.HTTPError,
    *,
    timeout_message: str,
    request_failed_message: str,
) -> MCPToolError:
    if isinstance(exception, httpx2.TimeoutException):
        return MCPToolError(-32603, timeout_message)
    return MCPToolError(-32603, request_failed_message)


def parse_provider_json_dict(body: bytes, *, field: str, invalid_message: str) -> JSONDict:
    try:
        return parse_json_dict(body, field=field)
    except ValidationError as exception:
        raise MCPToolError(-32603, invalid_message) from exception


async def read_provider_response_bytes(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    url: str,
    extensions: dict[str, str] | None,
    timeout_sec: float,
    max_response_bytes: int,
    exceeded_size_message: str,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, int, str | None]:
    if utility_tools.http_client is None:
        raise MCPToolError(-32603, "HTTP client is not available")
    async with utility_tools.http_client.stream(
        method="GET",
        url=url,
        headers=headers,
        timeout=float(timeout_sec),
        follow_redirects=False,
        extensions=extensions,
    ) as response:
        body, truncated = await read_response_body_with_limit(
            response,
            max_response_bytes=max_response_bytes,
        )
        if truncated:
            raise MCPToolError(-32603, exceeded_size_message)
        return body, int(response.status_code), read_retry_after_header(response)

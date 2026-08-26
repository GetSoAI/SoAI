"""SoAI - GDELT downloadable feed HTTP access [backend/mcp/tools/news_gdelt_feed_http.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.exceptions import ValidationError
from core.network.http_transport import build_pinned_host_extensions
from mcp.tools.error import MCPToolError
from mcp.tools.offline_policy import (
    is_offline_mode_enabled,
    require_url_allowed_when_offline,
)
from mcp.tools.private_egress import resolve_private_egress_pinned_host
from mcp.tools.provider_http import read_provider_response_bytes

if TYPE_CHECKING:
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("read_gdelt_feed_response",)


async def _resolve_feed_extensions(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    url: str,
) -> dict[str, str] | None:
    pinned_host = await require_url_allowed_when_offline(
        utility_tools.runtime_flags,
        tool_name="news",
        url=url,
        capability="GDELT downloadable news feed access",
    )
    try:
        enforced_pinned_host = await resolve_private_egress_pinned_host(
            url=url,
            egress_blocking_enabled=bool(
                utility_tools.config.get_bool("TOOLS.MCP.NEWS.BLOCK_PRIVATE_NETWORK_EGRESS"),
            ),
            offline_mode_enabled=is_offline_mode_enabled(utility_tools.runtime_flags),
            dns_timeout_value=utility_tools.config.get("TOOLS.MCP.NEWS.DNS_TIMEOUT_SEC"),
            source="MCP news GDELT downloadable feed",
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, "News provider network policy blocked access.") from exception
    if enforced_pinned_host is not None:
        pinned_host = enforced_pinned_host
    if pinned_host is None:
        return None
    original_host = urlparse(url).hostname
    if not original_host:
        raise MCPToolError(-32602, "News provider URL must include a hostname.")
    return build_pinned_host_extensions(pinned_host, original_host)


async def read_gdelt_feed_response(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    url: str,
    timeout_sec: float,
    max_response_bytes: int,
) -> tuple[bytes, int]:
    extensions = await _resolve_feed_extensions(utility_tools, url=url)
    body, status_code, _ = await read_provider_response_bytes(
        utility_tools,
        url=url,
        extensions=extensions,
        timeout_sec=timeout_sec,
        max_response_bytes=max_response_bytes,
        exceeded_size_message="News provider response exceeded size limit.",
        headers={"User-Agent": "SoAI/1.0 news tool"},
    )
    return body, status_code

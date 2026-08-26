"""SoAI - MCP HTTP request target policy [backend/mcp/tools/http_request_target_policy.py]"""
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

if TYPE_CHECKING:
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("resolve_http_request_target_extensions",)


async def resolve_http_request_target_extensions(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    url: str,
) -> dict[str, str] | None:
    pinned_host = await require_url_allowed_when_offline(
        utility_tools.runtime_flags,
        tool_name="http_request",
        url=url,
        capability="http_request outbound HTTP",
    )
    try:
        enforced_pinned_host = await resolve_private_egress_pinned_host(
            url=url,
            egress_blocking_enabled=utility_tools.config.get_bool(
                "TOOLS.MCP.HTTP_REQUEST.BLOCK_PRIVATE_NETWORK_EGRESS"
            ),
            offline_mode_enabled=is_offline_mode_enabled(utility_tools.runtime_flags),
            dns_timeout_value=utility_tools.config.get("TOOLS.MCP.HTTP_REQUEST.DNS_TIMEOUT_SEC"),
            source="MCP http_request",
        )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    if enforced_pinned_host is not None:
        pinned_host = enforced_pinned_host
    if pinned_host is None:
        return None
    original_host = urlparse(url).hostname
    if original_host is None:
        raise MCPToolError(-32602, "URL must include a hostname.")
    return build_pinned_host_extensions(pinned_host, original_host)

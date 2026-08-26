"""SoAI - MCP HTTP header construction helpers [backend/mcp/protocol/http_headers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from mcp.protocol.types import MCPServerConfig

__all__ = ("build_mcp_http_headers",)


def build_mcp_http_headers(
    config: MCPServerConfig,
    *,
    protocol_version: str,
    decrypt_secret: Callable[[str], str | None],
) -> dict[str, str]:
    headers: dict[str, str] = {
        "MCP-Protocol-Version": protocol_version,
        **(config.headers or {}),
    }
    if config.auth_type == "api_key" and config.api_key_encrypted:
        if api_key := decrypt_secret(config.api_key_encrypted):
            headers["Authorization"] = f"Bearer {api_key}"
    if config.auth_type == "oauth" and config.oauth_access_token_encrypted:
        if access_token := decrypt_secret(config.oauth_access_token_encrypted):
            headers["Authorization"] = f"Bearer {access_token}"
    return headers

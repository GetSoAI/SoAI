"""SoAI - MCP server configuration record [backend/core/mcp/server_config_record.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("MCPServerConfigRecord",)


@dataclass(frozen=True, slots=True)
class MCPServerConfigRecord:
    id: str
    name: str
    transport_type: str
    endpoint: str
    args: list[str] | None
    env: dict[str, str] | None
    headers: dict[str, str] | None
    auth_type: str
    api_key_encrypted: str | None
    oauth_status: str
    oauth_client_id: str | None
    oauth_client_secret_encrypted: str | None
    oauth_access_token_encrypted: str | None
    oauth_refresh_token_encrypted: str | None
    oauth_expires_at_ms: int | None
    oauth_resource_metadata_url: str | None
    oauth_auth_server_issuer: str | None
    oauth_authorization_endpoint: str | None
    oauth_token_endpoint: str | None
    oauth_registration_endpoint: str | None
    oauth_token_endpoint_auth_method: str | None
    oauth_scopes: list[str] | None
    oauth_required_scopes: list[str] | None
    timeout_sec: int
    auto_reconnect: bool
    enabled: bool

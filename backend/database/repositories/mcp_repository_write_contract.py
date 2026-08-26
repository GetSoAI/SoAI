"""SoAI - MCP server write contract constants [backend/database/repositories/mcp_repository_write_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "ALLOWED_MCP_SERVER_UPDATE_COLS",
    "ALLOWED_MCP_SERVER_UPDATE_SQL_COLS",
    "ALLOWED_MCP_TRANSPORT_TYPES",
)

ALLOWED_MCP_SERVER_UPDATE_COLS: frozenset[str] = frozenset(
    {
        "name",
        "transport_type",
        "endpoint",
        "args",
        "env",
        "headers",
        "auth_type",
        "api_key",
        "oauth_authorization_endpoint",
        "oauth_token_endpoint",
        "oauth_registration_endpoint",
        "oauth_auth_server_issuer",
        "oauth_resource_metadata_url",
        "oauth_scopes",
        "oauth_required_scopes",
        "oauth_status",
        "oauth_client_id",
        "oauth_client_secret",
        "oauth_access_token",
        "oauth_refresh_token",
        "oauth_expires_at_ms",
        "oauth_token_endpoint_auth_method",
        "timeout_ms",
        "auto_reconnect",
        "enabled",
    },
)

ALLOWED_MCP_TRANSPORT_TYPES: frozenset[str] = frozenset(("stdio", "streamable_http"))

ALLOWED_MCP_SERVER_UPDATE_SQL_COLS: frozenset[str] = frozenset(
    {
        "args",
        "auth_type",
        "auto_reconnect",
        "enabled",
        "endpoint",
        "env",
        "headers",
        "name",
        "oauth_access_token",
        "oauth_access_token_encrypted",
        "oauth_refresh_token",
        "oauth_refresh_token_encrypted",
        "oauth_expires_at_ms",
        "oauth_status",
        "oauth_client_secret_encrypted",
        "oauth_client_secret",
        "oauth_client_id",
        "oauth_required_scopes",
        "oauth_scopes",
        "oauth_token_endpoint_auth_method",
        "oauth_registration_endpoint",
        "oauth_token_endpoint",
        "oauth_authorization_endpoint",
        "oauth_auth_server_issuer",
        "oauth_resource_metadata_url",
        "timeout_ms",
        "transport_type",
        "api_key",
        "api_key_encrypted",
        "last_modified_at_ms",
    },
)

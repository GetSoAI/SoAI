"""SoAI - MCP server config record to runtime config conversion [backend/mcp/remote/config_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.mcp.server_config_normalization import (
    normalize_server_config,
    normalize_server_config_row,
)
from core.mcp.server_config_record import MCPServerConfigRecord
from mcp.protocol.types import MCPServerConfig, MCPTransportType

if TYPE_CHECKING:
    from core.mcp.protocols_storage import MCPServerConfigProtocol
    from core.types.json import JSONValue

__all__ = (
    "coerce_to_mcp_server_config",
    "mcp_server_config_from_db_row",
)


def _resolve_transport_type(transport_type: str) -> MCPTransportType:
    try:
        return MCPTransportType(transport_type)
    except ValueError as exception:
        raise StateError(
            "MCP server config contains invalid transport_type.",
            details={"transport_type": transport_type},
        ) from exception


def _to_mcp_server_config(record: MCPServerConfigRecord) -> MCPServerConfig:
    return MCPServerConfig(
        id=record.id,
        name=record.name,
        transport_type=_resolve_transport_type(record.transport_type),
        endpoint=record.endpoint,
        args=list(record.args) if record.args is not None else None,
        env=dict(record.env) if record.env is not None else None,
        headers=dict(record.headers) if record.headers is not None else None,
        auth_type=record.auth_type,
        api_key_encrypted=record.api_key_encrypted,
        oauth_status=record.oauth_status,
        oauth_client_id=record.oauth_client_id,
        oauth_client_secret_encrypted=record.oauth_client_secret_encrypted,
        oauth_access_token_encrypted=record.oauth_access_token_encrypted,
        oauth_refresh_token_encrypted=record.oauth_refresh_token_encrypted,
        oauth_expires_at_ms=record.oauth_expires_at_ms,
        oauth_resource_metadata_url=record.oauth_resource_metadata_url,
        oauth_auth_server_issuer=record.oauth_auth_server_issuer,
        oauth_authorization_endpoint=record.oauth_authorization_endpoint,
        oauth_token_endpoint=record.oauth_token_endpoint,
        oauth_registration_endpoint=record.oauth_registration_endpoint,
        oauth_token_endpoint_auth_method=record.oauth_token_endpoint_auth_method,
        oauth_scopes=tuple(record.oauth_scopes) if record.oauth_scopes is not None else None,
        oauth_required_scopes=(
            tuple(record.oauth_required_scopes)
            if record.oauth_required_scopes is not None
            else None
        ),
        timeout_sec=record.timeout_sec,
        auto_reconnect=record.auto_reconnect,
        enabled=record.enabled,
    )


def coerce_to_mcp_server_config(config: MCPServerConfigProtocol) -> MCPServerConfig:
    return _to_mcp_server_config(normalize_server_config(config))


def mcp_server_config_from_db_row(row: Mapping[str, JSONValue]) -> MCPServerConfig:
    return _to_mcp_server_config(normalize_server_config_row(row))

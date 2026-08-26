"""SoAI - Canonical MCP server config normalization [backend/core/mcp/server_config_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.mcp.protocols_storage import MCPServerConfigProtocol
from core.mcp.qualified_name import is_valid_qualified_server_id
from core.mcp.server_config_fields import (
    coerce_config_bool,
    coerce_optional_config_int,
    coerce_optional_config_str,
    coerce_optional_config_str_dict,
    coerce_optional_config_str_list,
    coerce_optional_row_int,
    coerce_optional_row_str,
    coerce_optional_row_str_dict,
    coerce_optional_row_str_list,
    coerce_row_bool,
    coerce_timeout_sec_from_row,
    normalize_config_auth_type,
    normalize_config_oauth_status,
    normalize_row_auth_type,
    normalize_row_oauth_status,
    require_non_empty_config_str,
    require_non_empty_row_str,
)
from core.mcp.server_config_record import MCPServerConfigRecord

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "normalize_server_config",
    "normalize_server_config_row",
    "require_valid_server_id",
)


def require_valid_server_id(value: str) -> str:
    normalized = value.strip()
    if not is_valid_qualified_server_id(normalized):
        raise StateError("MCP server config field 'id' is invalid.")
    return normalized


def normalize_server_config_row(row: Mapping[str, JSONValue]) -> MCPServerConfigRecord:
    normalized_server_id = require_valid_server_id(
        require_non_empty_row_str(row.get("id"), field_name="id"),
    )
    return MCPServerConfigRecord(
        id=normalized_server_id,
        name=require_non_empty_row_str(row.get("name"), field_name="name"),
        transport_type=require_non_empty_row_str(
            row.get("transport_type"),
            field_name="transport_type",
        ),
        endpoint=require_non_empty_row_str(row.get("endpoint"), field_name="endpoint"),
        args=coerce_optional_row_str_list(row.get("args"), field_name="args"),
        env=coerce_optional_row_str_dict(row.get("env"), field_name="env"),
        headers=coerce_optional_row_str_dict(row.get("headers"), field_name="headers"),
        auth_type=normalize_row_auth_type(row.get("auth_type")),
        api_key_encrypted=coerce_optional_row_str(row.get("api_key_encrypted")),
        oauth_status=normalize_row_oauth_status(row.get("oauth_status")),
        oauth_client_id=coerce_optional_row_str(row.get("oauth_client_id")),
        oauth_client_secret_encrypted=coerce_optional_row_str(
            row.get("oauth_client_secret_encrypted"),
        ),
        oauth_access_token_encrypted=coerce_optional_row_str(
            row.get("oauth_access_token_encrypted"),
        ),
        oauth_refresh_token_encrypted=coerce_optional_row_str(
            row.get("oauth_refresh_token_encrypted"),
        ),
        oauth_expires_at_ms=coerce_optional_row_int(
            row.get("oauth_expires_at_ms"),
            field_name="oauth_expires_at_ms",
        ),
        oauth_resource_metadata_url=coerce_optional_row_str(row.get("oauth_resource_metadata_url")),
        oauth_auth_server_issuer=coerce_optional_row_str(row.get("oauth_auth_server_issuer")),
        oauth_authorization_endpoint=coerce_optional_row_str(
            row.get("oauth_authorization_endpoint"),
        ),
        oauth_token_endpoint=coerce_optional_row_str(row.get("oauth_token_endpoint")),
        oauth_registration_endpoint=coerce_optional_row_str(row.get("oauth_registration_endpoint")),
        oauth_token_endpoint_auth_method=coerce_optional_row_str(
            row.get("oauth_token_endpoint_auth_method"),
        ),
        oauth_scopes=coerce_optional_row_str_list(
            row.get("oauth_scopes"),
            field_name="oauth_scopes",
        ),
        oauth_required_scopes=coerce_optional_row_str_list(
            row.get("oauth_required_scopes"),
            field_name="oauth_required_scopes",
        ),
        timeout_sec=coerce_timeout_sec_from_row(row.get("timeout_ms"), field_name="timeout_ms"),
        auto_reconnect=coerce_row_bool(row.get("auto_reconnect"), default=True),
        enabled=coerce_row_bool(row.get("enabled"), default=True),
    )


def normalize_server_config(config: MCPServerConfigProtocol) -> MCPServerConfigRecord:
    transport_value = config.transport_type
    transport_type = (
        str(transport_value.value) if isinstance(transport_value, Enum) else str(transport_value)
    )
    return MCPServerConfigRecord(
        id=require_valid_server_id(config.id),
        name=require_non_empty_config_str(config.name, field_name="name"),
        transport_type=require_non_empty_config_str(transport_type, field_name="transport_type"),
        endpoint=require_non_empty_config_str(config.endpoint, field_name="endpoint"),
        args=coerce_optional_config_str_list(config.args, field_name="args"),
        env=coerce_optional_config_str_dict(config.env, field_name="env"),
        headers=coerce_optional_config_str_dict(config.headers, field_name="headers"),
        auth_type=normalize_config_auth_type(
            require_non_empty_config_str(str(config.auth_type), field_name="auth_type"),
        ),
        api_key_encrypted=coerce_optional_config_str(
            config.api_key_encrypted,
            field_name="api_key_encrypted",
        ),
        oauth_status=normalize_config_oauth_status(
            require_non_empty_config_str(
                str(config.oauth_status),
                field_name="oauth_status",
            ),
        ),
        oauth_client_id=coerce_optional_config_str(
            config.oauth_client_id,
            field_name="oauth_client_id",
        ),
        oauth_client_secret_encrypted=coerce_optional_config_str(
            config.oauth_client_secret_encrypted,
            field_name="oauth_client_secret_encrypted",
        ),
        oauth_access_token_encrypted=coerce_optional_config_str(
            config.oauth_access_token_encrypted,
            field_name="oauth_access_token_encrypted",
        ),
        oauth_refresh_token_encrypted=coerce_optional_config_str(
            config.oauth_refresh_token_encrypted,
            field_name="oauth_refresh_token_encrypted",
        ),
        oauth_expires_at_ms=coerce_optional_config_int(
            config.oauth_expires_at_ms,
            field_name="oauth_expires_at_ms",
            minimum=0,
        ),
        oauth_resource_metadata_url=coerce_optional_config_str(
            config.oauth_resource_metadata_url,
            field_name="oauth_resource_metadata_url",
        ),
        oauth_auth_server_issuer=coerce_optional_config_str(
            config.oauth_auth_server_issuer,
            field_name="oauth_auth_server_issuer",
        ),
        oauth_authorization_endpoint=coerce_optional_config_str(
            config.oauth_authorization_endpoint,
            field_name="oauth_authorization_endpoint",
        ),
        oauth_token_endpoint=coerce_optional_config_str(
            config.oauth_token_endpoint,
            field_name="oauth_token_endpoint",
        ),
        oauth_registration_endpoint=coerce_optional_config_str(
            config.oauth_registration_endpoint,
            field_name="oauth_registration_endpoint",
        ),
        oauth_token_endpoint_auth_method=coerce_optional_config_str(
            config.oauth_token_endpoint_auth_method,
            field_name="oauth_token_endpoint_auth_method",
        ),
        oauth_scopes=coerce_optional_config_str_list(
            config.oauth_scopes,
            field_name="oauth_scopes",
        ),
        oauth_required_scopes=coerce_optional_config_str_list(
            config.oauth_required_scopes,
            field_name="oauth_required_scopes",
        ),
        timeout_sec=coerce_optional_config_int(
            config.timeout_sec,
            field_name="timeout_sec",
            minimum=1,
        )
        or 30,
        auto_reconnect=coerce_config_bool(
            config.auto_reconnect,
            field_name="auto_reconnect",
            default=True,
        ),
        enabled=coerce_config_bool(
            config.enabled,
            field_name="enabled",
            default=True,
        ),
    )

"""SoAI - MCP server write payload normalization and serialization [backend/database/repositories/mcp_repository_write_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from cryptography.fernet import Fernet

from core.errors.exceptions import ValidationError
from core.external_accounts.state import coerce_oauth_status
from core.mcp.server_config_normalization import require_valid_server_id
from core.mcp.server_write_fields import (
    coerce_mcp_auth_type,
    coerce_mcp_optional_epoch_ms,
    coerce_mcp_optional_secret_text,
    coerce_mcp_optional_str_dict,
    coerce_mcp_optional_str_list,
    coerce_mcp_optional_text,
    coerce_mcp_required_bool_flag,
    coerce_mcp_required_text,
    coerce_mcp_timeout_ms,
    coerce_mcp_transport_type,
)
from core.security.secret_crypto import encrypt_optional_secret
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from database.core.sqlite_values import SQLiteValue
from database.repositories.mcp_repository_write_contract import (
    ALLOWED_MCP_SERVER_UPDATE_COLS,
    ALLOWED_MCP_TRANSPORT_TYPES,
)
from database.repositories.mcp_repository_write_redacted_mappings import (
    load_existing_json_str_mapping,
    merge_redacted_mapping_update,
)
from database.repositories.mcp_repository_writes_support import (
    serialize_optional_scopes_json,
)

__all__ = (
    "PreparedMCPServerInsert",
    "PreparedMCPServerUpdate",
    "prepare_mcp_server_insert_payload",
    "prepare_mcp_server_update_payload",
)


@dataclass(frozen=True, slots=True)
class PreparedMCPServerInsert:
    server_id: str
    values: tuple[SQLiteValue, ...]


@dataclass(frozen=True, slots=True)
class PreparedMCPServerUpdate:
    server_id: str
    updates_sql: dict[str, SQLiteValue]


def prepare_mcp_server_insert_payload(
    fernet: tuple[Fernet, ...],
    *,
    server_id: str,
    name: str,
    transport_type: str,
    endpoint: str,
    args: list[str] | None,
    env: dict[str, str] | None,
    headers: dict[str, str] | None,
    api_key: str | None,
    timeout_ms: int,
    auto_reconnect: bool,
) -> PreparedMCPServerInsert:
    normalized_server_id = require_valid_server_id(server_id)
    normalized_name = coerce_mcp_required_text(name, "name")
    normalized_transport_type = coerce_mcp_transport_type(
        transport_type,
        allowed_transport_types=ALLOWED_MCP_TRANSPORT_TYPES,
    )
    normalized_endpoint = coerce_mcp_required_text(endpoint, "endpoint")
    normalized_api_key = coerce_mcp_optional_secret_text(api_key, "api_key")
    validated_timeout = coerce_mcp_timeout_ms(timeout_ms)
    auto_reconnect_flag = coerce_mcp_required_bool_flag(auto_reconnect, "auto_reconnect")
    encrypted_key = encrypt_optional_secret(
        fernet,
        normalized_api_key,
        label="mcp api_key",
    )
    auth_type = "api_key" if encrypted_key else "none"
    now = epoch_ms()
    return PreparedMCPServerInsert(
        server_id=normalized_server_id,
        values=(
            normalized_server_id,
            normalized_name,
            normalized_transport_type,
            normalized_endpoint,
            (
                serialize_json_compact_stable_strict(coerce_mcp_optional_str_list(args, "args"))
                if args is not None
                else None
            ),
            (
                serialize_json_compact_stable_strict(coerce_mcp_optional_str_dict(env, "env"))
                if env is not None
                else None
            ),
            (
                serialize_json_compact_stable_strict(
                    coerce_mcp_optional_str_dict(headers, "headers"),
                )
                if headers is not None
                else None
            ),
            auth_type,
            encrypted_key,
            validated_timeout,
            auto_reconnect_flag,
            now,
            now,
        ),
    )


def prepare_mcp_server_update_payload(
    conn: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
    *,
    server_id: str,
    updates: JSONDict,
) -> PreparedMCPServerUpdate:
    normalized_server_id = require_valid_server_id(server_id)
    invalid_cols = set(updates.keys()) - ALLOWED_MCP_SERVER_UPDATE_COLS
    if invalid_cols:
        raise ValidationError(f"Invalid column names for MCP server update: {invalid_cols}")
    updates_sql: dict[str, SQLiteValue] = {}
    if "api_key" in updates:
        api_key_plaintext = coerce_mcp_optional_secret_text(updates.get("api_key"), "api_key")
        updates_sql["api_key_encrypted"] = encrypt_optional_secret(
            fernet,
            api_key_plaintext,
            label="mcp api_key",
        )
        if "auth_type" not in updates:
            updates_sql["auth_type"] = "api_key" if api_key_plaintext else "none"
    if "auth_type" in updates:
        updates_sql["auth_type"] = coerce_mcp_auth_type(updates.get("auth_type"))
    if "oauth_status" in updates:
        updates_sql["oauth_status"] = coerce_oauth_status(updates.get("oauth_status"))
    if "oauth_client_id" in updates:
        updates_sql["oauth_client_id"] = coerce_mcp_optional_text(
            updates.get("oauth_client_id"),
            "oauth_client_id",
        )
    if "oauth_client_secret" in updates:
        updates_sql["oauth_client_secret_encrypted"] = encrypt_optional_secret(
            fernet,
            coerce_mcp_optional_secret_text(
                updates.get("oauth_client_secret"),
                "oauth_client_secret",
            ),
            label="mcp oauth_client_secret",
        )
    if "oauth_access_token" in updates:
        updates_sql["oauth_access_token_encrypted"] = encrypt_optional_secret(
            fernet,
            coerce_mcp_optional_secret_text(
                updates.get("oauth_access_token"),
                "oauth_access_token",
            ),
            label="mcp oauth_access_token",
        )
    if "oauth_refresh_token" in updates:
        updates_sql["oauth_refresh_token_encrypted"] = encrypt_optional_secret(
            fernet,
            coerce_mcp_optional_secret_text(
                updates.get("oauth_refresh_token"),
                "oauth_refresh_token",
            ),
            label="mcp oauth_refresh_token",
        )
    if "oauth_expires_at_ms" in updates:
        updates_sql["oauth_expires_at_ms"] = coerce_mcp_optional_epoch_ms(
            updates.get("oauth_expires_at_ms"),
            "oauth_expires_at_ms",
        )
    if "oauth_resource_metadata_url" in updates:
        updates_sql["oauth_resource_metadata_url"] = coerce_mcp_optional_text(
            updates.get("oauth_resource_metadata_url"),
            "oauth_resource_metadata_url",
        )
    if "oauth_auth_server_issuer" in updates:
        updates_sql["oauth_auth_server_issuer"] = coerce_mcp_optional_text(
            updates.get("oauth_auth_server_issuer"),
            "oauth_auth_server_issuer",
        )
    if "oauth_authorization_endpoint" in updates:
        updates_sql["oauth_authorization_endpoint"] = coerce_mcp_optional_text(
            updates.get("oauth_authorization_endpoint"),
            "oauth_authorization_endpoint",
        )
    if "oauth_token_endpoint" in updates:
        updates_sql["oauth_token_endpoint"] = coerce_mcp_optional_text(
            updates.get("oauth_token_endpoint"),
            "oauth_token_endpoint",
        )
    if "oauth_registration_endpoint" in updates:
        updates_sql["oauth_registration_endpoint"] = coerce_mcp_optional_text(
            updates.get("oauth_registration_endpoint"),
            "oauth_registration_endpoint",
        )
    if "oauth_token_endpoint_auth_method" in updates:
        updates_sql["oauth_token_endpoint_auth_method"] = coerce_mcp_optional_text(
            updates.get("oauth_token_endpoint_auth_method"),
            "oauth_token_endpoint_auth_method",
        )
    if "oauth_scopes" in updates:
        updates_sql["oauth_scopes"] = serialize_optional_scopes_json(updates.get("oauth_scopes"))
    if "oauth_required_scopes" in updates:
        updates_sql["oauth_required_scopes"] = serialize_optional_scopes_json(
            updates.get("oauth_required_scopes"),
        )
    if "name" in updates:
        updates_sql["name"] = coerce_mcp_required_text(updates.get("name"), "name")
    if "transport_type" in updates:
        updates_sql["transport_type"] = coerce_mcp_transport_type(
            updates.get("transport_type"),
            allowed_transport_types=ALLOWED_MCP_TRANSPORT_TYPES,
        )
    if "endpoint" in updates:
        updates_sql["endpoint"] = coerce_mcp_required_text(updates.get("endpoint"), "endpoint")
    if "args" in updates:
        args_value = coerce_mcp_optional_str_list(updates.get("args"), "args")
        updates_sql["args"] = (
            serialize_json_compact_stable_strict(args_value) if args_value is not None else None
        )
    if "env" in updates:
        updates_sql["env"] = _resolve_mapping_update(
            conn,
            server_id=normalized_server_id,
            column="env",
            value=updates.get("env"),
        )
    if "headers" in updates:
        updates_sql["headers"] = _resolve_mapping_update(
            conn,
            server_id=normalized_server_id,
            column="headers",
            value=updates.get("headers"),
        )
    if "timeout_ms" in updates:
        updates_sql["timeout_ms"] = coerce_mcp_timeout_ms(updates.get("timeout_ms"))
    if "auto_reconnect" in updates:
        updates_sql["auto_reconnect"] = coerce_mcp_required_bool_flag(
            updates.get("auto_reconnect"),
            "auto_reconnect",
        )
    if "enabled" in updates:
        updates_sql["enabled"] = coerce_mcp_required_bool_flag(updates.get("enabled"), "enabled")
    updates_sql["last_modified_at_ms"] = epoch_ms()
    return PreparedMCPServerUpdate(server_id=normalized_server_id, updates_sql=updates_sql)


def _resolve_mapping_update(
    conn: sqlite3.Connection,
    *,
    server_id: str,
    column: str,
    value: JSONValue,
) -> SQLiteValue:
    if isinstance(value, dict):
        existing_mapping = load_existing_json_str_mapping(
            conn,
            server_id=server_id,
            column=column,
        )
        merged_mapping = merge_redacted_mapping_update(
            existing=existing_mapping,
            incoming=value,
            column=column,
        )
        return serialize_json_compact_stable_strict(merged_mapping)
    normalized_mapping = coerce_mcp_optional_str_dict(value, column)
    if normalized_mapping is None:
        return None
    return serialize_json_compact_stable_strict(normalized_mapping)

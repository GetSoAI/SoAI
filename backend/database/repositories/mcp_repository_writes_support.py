"""SoAI - MCP repository write helpers (status, capabilities, scopes) [backend/database/repositories/mcp_repository_writes_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from core.mcp.server_config_normalization import require_valid_server_id
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_str_list

__all__ = (
    "serialize_mcp_capabilities",
    "sync_update_mcp_server_capabilities",
    "sync_update_mcp_server_status",
)


def sync_update_mcp_server_status(
    conn: sqlite3.Connection,
    server_id: str,
    status: str,
    error: str | None = None,
) -> bool:
    now = epoch_ms()
    normalized_server_id = require_valid_server_id(server_id)
    return (
        conn.execute(
            "UPDATE mcp_servers SET status = ?, last_error = ?, last_modified_at_ms = ? WHERE id = ?",
            (status, error, now, normalized_server_id),
        ).rowcount
        > 0
    )


def serialize_mcp_capabilities(capabilities: JSONDict | None) -> str | None:
    if capabilities is None:
        return None
    try:
        return serialize_json_compact_stable_strict(capabilities)
    except (TypeError, ValueError) as exception:
        raise ValidationError("MCP server capabilities must be JSON-serializable.") from exception


def sync_update_mcp_server_capabilities(
    conn: sqlite3.Connection,
    server_id: str,
    capabilities_json: str | None,
) -> bool:
    now = epoch_ms()
    normalized_server_id = require_valid_server_id(server_id)
    return (
        conn.execute(
            "UPDATE mcp_servers SET capabilities = ?, last_modified_at_ms = ? WHERE id = ?",
            (capabilities_json, now, normalized_server_id),
        ).rowcount
        > 0
    )


def serialize_optional_scopes_json(value: JSONValue | None) -> str | None:
    if value is None:
        return None
    scopes = coerce_str_list(value, strip_items=True)
    if scopes is None:
        raise ValidationError("Scopes must be a JSON array of strings.")
    filtered_scopes = [scope for scope in scopes if scope]
    try:
        return serialize_json_compact_stable_strict(filtered_scopes)
    except (TypeError, ValueError) as exception:
        raise ValidationError("Scopes must be JSON-serializable.") from exception

"""SoAI - MCP server writes for redacted environment and header mappings [backend/database/repositories/mcp_repository_write_redacted_mappings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.security.response_redaction import REDACTED_PLACEHOLDER
from core.serialization.json_parsing import parse_json_dict
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sql_builders import validate_sql_identifier

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "load_existing_json_str_mapping",
    "merge_redacted_mapping_update",
)


def load_existing_json_str_mapping(
    conn: sqlite3.Connection,
    *,
    server_id: str,
    column: str,
) -> dict[str, str]:
    if column not in {"env", "headers"}:
        raise ValidationError("Invalid mapping column for MCP server update.")
    column_name = validate_sql_identifier(column, label="column")
    row = sync_fetch_one_as_dict(
        conn.execute(f"SELECT {column_name} FROM mcp_servers WHERE id = ?", (server_id,)),
    )
    raw_value = row.get(column_name) if row else None
    if not (isinstance(raw_value, str) and raw_value):
        return {}
    try:
        parsed = parse_json_dict(raw_value, field=column)
    except ValidationError as exception:
        raise ValidationError(f"Failed to decode existing {column} JSON.") from exception
    normalized: dict[str, str] = {}
    for key, raw_val in parsed.items():
        if not key:
            raise ValidationError(f"Stored {column} contains an empty key.")
        if not isinstance(raw_val, str):
            raise ValidationError(f"Stored {column} contains a non-string value.")
        normalized[key] = raw_val
    return normalized


def merge_redacted_mapping_update(
    *,
    existing: dict[str, str],
    incoming: JSONDict,
    column: str,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    for raw_key, raw_val in incoming.items():
        if not isinstance(raw_key, str) or not raw_key:
            raise ValidationError(f"{column} contains an empty key.")
        key_str = raw_key
        if raw_val == REDACTED_PLACEHOLDER:
            if key_str not in existing:
                raise ValidationError(
                    f"{column} contains redacted placeholder for unknown key '{key_str}'.",
                )
            merged[key_str] = existing[key_str]
            continue
        if not isinstance(raw_val, str):
            raise ValidationError(f"{column} values must be strings.")
        merged[key_str] = raw_val
    return merged

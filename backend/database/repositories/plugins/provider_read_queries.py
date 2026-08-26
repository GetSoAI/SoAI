"""SoAI - External provider row formatting and read queries [backend/database/repositories/plugins/provider_read_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite
from cryptography.fernet import Fernet

from core.errors.exceptions import ValidationError
from core.models.external_provider_record import (
    ExternalProviderInternalRecord,
    coerce_external_provider_internal_record,
)
from core.types.json import JSONDict, JSONValue
from core.types.json_value import coerce_str_dict, coerce_str_list
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_one_as_dict,
)
from database.repositories.row_formatting import format_api_key_field, format_row

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "format_provider_row",
    "get_all_external_providers_query",
    "get_external_provider_async_query",
    "list_providers_for_plugin_query",
    "sync_get_external_provider",
)


def format_provider_row(
    row: SQLiteRowDict | None,
    fernet: tuple[Fernet, ...],
    decrypt_key: bool = False,
) -> ExternalProviderInternalRecord | None:
    formatted = format_row(row)
    if formatted is None:
        return None
    format_api_key_field(
        formatted,
        fernet,
        encrypted_column="api_key",
        output_key="api_key",
        decrypt_key=decrypt_key,
    )
    models_filter_value: JSONValue = (
        safe_json_deserialize(row.get("models_filter"), []) if row is not None else []
    )
    models_filter = coerce_str_list(models_filter_value)
    if models_filter is None:
        raise ValidationError("External provider row models_filter is invalid.")
    formatted["models_filter"] = models_filter
    headers_value: JSONValue = (
        safe_json_deserialize(row.get("extra_headers"), {}) if row is not None else {}
    )
    headers = coerce_str_dict(headers_value)
    if headers is None:
        raise ValidationError("External provider row extra_headers is invalid.")
    formatted["extra_headers"] = headers
    query_value: JSONValue = (
        safe_json_deserialize(row.get("extra_query_params"), {}) if row is not None else {}
    )
    query_params = coerce_str_dict(query_value)
    if query_params is None:
        raise ValidationError("External provider row extra_query_params is invalid.")
    formatted["extra_query_params"] = query_params
    return coerce_external_provider_internal_record(
        formatted,
        label="External provider row",
    )


def sync_get_external_provider(
    conn: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
    provider_id: str,
    decrypt_key: bool = False,
) -> ExternalProviderInternalRecord | None:
    cursor = conn.execute("SELECT * FROM models_external_providers WHERE id = ?", (provider_id,))
    row_dict = sync_fetch_one_as_dict(cursor)
    return format_provider_row(row_dict, fernet, decrypt_key=decrypt_key)


async def get_external_provider_async_query(
    database: aiosqlite.Connection,
    fernet: tuple[Fernet, ...],
    provider_id: str,
    decrypt_key: bool = False,
) -> ExternalProviderInternalRecord | None:
    row = await query_one_to_dict(
        database,
        "SELECT * FROM models_external_providers WHERE id = ?",
        (provider_id,),
    )
    return format_provider_row(row, fernet, decrypt_key=decrypt_key)


async def list_providers_for_plugin_query(
    database: aiosqlite.Connection,
    fernet: tuple[Fernet, ...],
    plugin_name: str,
) -> list[ExternalProviderInternalRecord]:
    rows = await query_to_dicts(
        database,
        "SELECT * FROM models_external_providers WHERE plugin_name = ? ORDER BY name",
        (plugin_name,),
    )
    return [formatted for row in rows if (formatted := format_provider_row(row, fernet))]


async def get_all_external_providers_query(
    database: aiosqlite.Connection,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        (
            "SELECT id, name, api_url, last_status, last_error, last_checked_at_ms, "
            "context_window_tokens, created_at_ms, revision FROM models_external_providers"
        ),
    )
    return [formatted for row in rows if (formatted := format_row(row))]

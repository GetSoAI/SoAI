"""SoAI - MCP repository read operations [backend/database/repositories/mcp_repository_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite
from cryptography.fernet import Fernet

from core.mcp.server_config_normalization import require_valid_server_id
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_one_as_dict,
)
from database.repositories.mcp_row_formatting import format_mcp_server_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_all_mcp_servers",
    "read_mcp_server",
    "sync_read_mcp_server",
)


async def read_all_mcp_servers(
    database: aiosqlite.Connection,
    fernet: tuple[Fernet, ...],
    *,
    decrypt_key: bool,
) -> list[JSONDict]:
    rows = await query_to_dicts(database, "SELECT * FROM mcp_servers ORDER BY created_at_ms DESC")
    return [
        formatted
        for row in rows
        if (formatted := format_mcp_server_row(row, fernet, decrypt_key=decrypt_key))
    ]


async def read_mcp_server(
    database: aiosqlite.Connection,
    server_id: str,
    fernet: tuple[Fernet, ...],
    *,
    decrypt_key: bool,
) -> JSONDict | None:
    normalized_server_id = require_valid_server_id(server_id)
    row = await query_one_to_dict(
        database,
        "SELECT * FROM mcp_servers WHERE id = ?",
        (normalized_server_id,),
    )
    return format_mcp_server_row(row, fernet, decrypt_key=decrypt_key)


def sync_read_mcp_server(
    conn: sqlite3.Connection,
    server_id: str,
    fernet: tuple[Fernet, ...],
    *,
    decrypt_key: bool,
) -> JSONDict | None:
    normalized_server_id = require_valid_server_id(server_id)
    cursor = conn.execute("SELECT * FROM mcp_servers WHERE id = ?", (normalized_server_id,))
    row_dict = sync_fetch_one_as_dict(cursor)
    return format_mcp_server_row(row_dict, fernet, decrypt_key=decrypt_key)

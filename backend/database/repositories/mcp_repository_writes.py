"""SoAI - Write operations for MCP server repository [backend/database/repositories/mcp_repository_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from cryptography.fernet import Fernet

from core.errors.exceptions import StateError, ValidationError
from core.mcp.server_config_normalization import require_valid_server_id
from core.state.errors import DuplicateMCPServerError
from core.types.json import JSONDict
from database.core.sql_builders import build_update_statement
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.mcp_repository_reads import sync_read_mcp_server
from database.repositories.mcp_repository_write_contract import (
    ALLOWED_MCP_SERVER_UPDATE_SQL_COLS,
)
from database.repositories.mcp_repository_write_payloads import (
    prepare_mcp_server_insert_payload,
    prepare_mcp_server_update_payload,
)

__all__ = (
    "sync_add_mcp_server",
    "sync_delete_mcp_server",
    "sync_update_mcp_server",
)


def sync_add_mcp_server(
    conn: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
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
) -> JSONDict | None:
    try:
        prepared_insert = prepare_mcp_server_insert_payload(
            fernet,
            server_id=server_id,
            name=name,
            transport_type=transport_type,
            endpoint=endpoint,
            args=args,
            env=env,
            headers=headers,
            api_key=api_key,
            timeout_ms=timeout_ms,
            auto_reconnect=auto_reconnect,
        )
        conn.execute(
            "INSERT INTO mcp_servers (id, name, transport_type, endpoint, args, env, headers, auth_type, api_key_encrypted, timeout_ms, auto_reconnect, enabled, status, created_at_ms, last_modified_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'disconnected', ?, ?)",
            prepared_insert.values,
        )
        return sync_read_mcp_server(conn, prepared_insert.server_id, fernet, decrypt_key=False)
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in ("unique", "primary_key"):
            raise DuplicateMCPServerError(
                f"MCP server with ID '{server_id}' already exists.",
            ) from exception
        if constraint_type in ("check", "not_null"):
            raise ValidationError(
                f"Invalid MCP server configuration: constraint violation on {detail or 'unknown field'}.",
            ) from exception
        raise StateError(f"Database constraint violation: {exception}") from exception


def sync_update_mcp_server(
    conn: sqlite3.Connection,
    fernet: tuple[Fernet, ...],
    server_id: str,
    updates: JSONDict,
) -> JSONDict | None:
    if not updates:
        return None
    prepared_update = prepare_mcp_server_update_payload(
        conn,
        fernet,
        server_id=server_id,
        updates=updates,
    )
    sql, params = build_update_statement(
        table="mcp_servers",
        updates=prepared_update.updates_sql,
        where_clause="id = ?",
        where_params=(prepared_update.server_id,),
        allowed_columns=ALLOWED_MCP_SERVER_UPDATE_SQL_COLS,
    )
    try:
        conn.execute(sql, params)
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type in ("check", "not_null"):
            raise ValidationError(
                f"Invalid MCP server update: constraint violation on {detail or 'unknown field'}.",
            ) from exception
        raise StateError(f"Database constraint violation: {exception}") from exception
    return sync_read_mcp_server(conn, prepared_update.server_id, fernet, decrypt_key=False)


def sync_delete_mcp_server(conn: sqlite3.Connection, server_id: str) -> bool:
    normalized_server_id = require_valid_server_id(server_id)
    return (
        conn.execute("DELETE FROM mcp_servers WHERE id = ?", (normalized_server_id,)).rowcount > 0
    )

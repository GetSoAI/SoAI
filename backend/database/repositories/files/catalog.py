"""SoAI - Database file catalog operations [backend/database/repositories/files/catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.files.database_types import (
    FileCatalogReconciliationRecord,
    FileCatalogRecord,
    FileCatalogRecordWithPath,
)
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from database.core.operations import sync_delete_by_ids
from database.core.query_execution import query_to_dicts
from database.core.sqlite_values import SQLiteValue
from database.repositories.files.record_parsing import (
    parse_file_catalog_reconciliation_record,
    parse_file_catalog_record,
    parse_file_catalog_record_with_path,
)
from database.repositories.owner_scope import normalize_owner_scope

__all__ = (
    "get_all_file_records_for_reconciliation_query",
    "get_file_info_query",
    "get_file_info_with_path_query",
    "sync_add_file",
    "sync_delete_file",
    "sync_delete_files_by_ids",
)


def sync_add_file(
    conn: sqlite3.Connection,
    file_id: str,
    filename: str,
    purpose: str,
    size_bytes: int,
    content_sha256: str,
    created_at_ms: int,
    file_path: str,
    user_id: int | None,
    api_key_id: str | None,
    status: str,
    status_details: str | None,
) -> bool:
    scope = normalize_owner_scope(user_id=user_id, api_key_id=api_key_id)
    canonical_content_sha256 = require_canonical_sha256_hexdigest(
        content_sha256,
        label="File catalog content_sha256",
    )
    conn.execute(
        "INSERT INTO files_catalog (id, filename, purpose, size_bytes, content_sha256, created_at_ms, file_path, user_id, api_key_id, status, status_details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            file_id,
            filename,
            purpose,
            size_bytes,
            canonical_content_sha256,
            created_at_ms,
            file_path,
            scope.user_id,
            scope.api_key_id,
            status,
            status_details,
        ),
    )
    return True


async def get_file_info_query(
    database: aiosqlite.Connection,
    file_id: str,
    *,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> FileCatalogRecord | None:
    scope = normalize_owner_scope(user_id=user_id, api_key_id=api_key_id)
    sql = """
        SELECT id, filename, purpose, size_bytes, content_sha256, created_at_ms, user_id, api_key_id, status, status_details
        FROM files_catalog
        WHERE id = ?
    """
    params: tuple[SQLiteValue, ...] = (file_id,)
    if enforce_owner:
        sql += "\n          AND user_id IS ?\n          AND api_key_id IS ?"
        params = (file_id, scope.user_id, scope.api_key_id)
    rows = await query_to_dicts(
        database,
        sql,
        params,
    )
    if not rows:
        return None
    return parse_file_catalog_record(rows[0])


async def get_file_info_with_path_query(
    database: aiosqlite.Connection,
    file_id: str,
    *,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> FileCatalogRecordWithPath | None:
    scope = normalize_owner_scope(user_id=user_id, api_key_id=api_key_id)
    sql = """
        SELECT *
        FROM files_catalog
        WHERE id = ?
    """
    params: tuple[SQLiteValue, ...] = (file_id,)
    if enforce_owner:
        sql += "\n          AND user_id IS ?\n          AND api_key_id IS ?"
        params = (file_id, scope.user_id, scope.api_key_id)
    rows = await query_to_dicts(
        database,
        sql,
        params,
    )
    if not rows:
        return None
    return parse_file_catalog_record_with_path(rows[0])


def sync_delete_file(
    conn: sqlite3.Connection,
    file_id: str,
    enforce_owner: bool = False,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> bool:
    scope = normalize_owner_scope(user_id=user_id, api_key_id=api_key_id)
    sql = "DELETE FROM files_catalog WHERE id = ?"
    params: tuple[SQLiteValue, ...] = (file_id,)
    if enforce_owner:
        sql += "\n  AND user_id IS ?\n  AND api_key_id IS ?"
        params = (file_id, scope.user_id, scope.api_key_id)
    return conn.execute(sql, params).rowcount > 0


async def get_all_file_records_for_reconciliation_query(
    database: aiosqlite.Connection,
) -> list[FileCatalogReconciliationRecord]:
    rows = await query_to_dicts(database, "SELECT id, file_path FROM files_catalog")
    return [parse_file_catalog_reconciliation_record(row) for row in rows]


def sync_delete_files_by_ids(
    conn: sqlite3.Connection,
    file_ids: list[str],
) -> int:
    return sync_delete_by_ids(conn, "files_catalog", "id", file_ids)

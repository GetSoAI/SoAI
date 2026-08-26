"""SoAI - SQLite directory listing snapshot queries [backend/features/file_explorer/directory_listing_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.files.directory_listing_models import (
    DirectoryListingEntryType,
    DirectoryListingSortColumn,
    DirectoryListingSortDirection,
)
from core.files.explorer_models import FileEntryInfo
from core.sqlite.connections import connect_sqlite
from features.file_explorer.directory_listing_snapshot import (
    SQLITE_BUSY_TIMEOUT_SECONDS,
)
from features.file_explorer.mime import classify_file_entry_type

__all__ = (
    "DirectoryListingQuery",
    "DirectoryListingSnapshotPage",
    "locate_directory_listing_entry",
    "read_directory_listing_page",
)


@dataclass(frozen=True, slots=True)
class DirectoryListingQuery:
    snapshot_path: str
    offset: int
    limit: int
    sort_column: DirectoryListingSortColumn
    sort_direction: DirectoryListingSortDirection
    entry_type: DirectoryListingEntryType


@dataclass(frozen=True, slots=True)
class DirectoryListingSnapshotPage:
    entries: list[FileEntryInfo]
    total: int
    has_more: bool
    next_offset: int | None


def _where_clause(entry_type: DirectoryListingEntryType) -> str:
    if entry_type == "directory":
        return " WHERE is_directory = 1"
    if entry_type == "file":
        return " WHERE is_directory = 0"
    return ""


def _order_clause(
    sort_column: DirectoryListingSortColumn,
    sort_direction: DirectoryListingSortDirection,
) -> str:
    direction = "ASC" if sort_direction == "asc" else "DESC"
    if sort_column == "type":
        return (
            f" ORDER BY type_rank {direction}, type_id {direction},"
            " name COLLATE NOCASE ASC, name ASC, ordinal ASC"
        )
    column = {
        "modified": "modified_at_ms",
        "name": "name COLLATE NOCASE",
        "size": "size",
    }[sort_column]
    name_tiebreaker = "" if sort_column == "name" else ", name COLLATE NOCASE ASC"
    return (
        f" ORDER BY is_directory DESC, {column} {direction}"
        f"{name_tiebreaker}, name ASC, ordinal ASC"
    )


def read_directory_listing_page(
    query: DirectoryListingQuery,
) -> DirectoryListingSnapshotPage:
    connection = connect_sqlite(
        query.snapshot_path,
        timeout=SQLITE_BUSY_TIMEOUT_SECONDS,
        must_exist=True,
    )
    try:
        where_clause = _where_clause(query.entry_type)
        total_row = connection.execute(
            f"SELECT COUNT(*) FROM entries{where_clause}",
        ).fetchone()
        total = int(total_row[0]) if total_row is not None else 0
        rows = connection.execute(
            (
                "SELECT name, is_directory, size, modified_at_ms, mime_type, type_rank,"
                " permissions"
                f" FROM entries{where_clause}"
                f"{_order_clause(query.sort_column, query.sort_direction)}"
                " LIMIT ? OFFSET ?"
            ),
            (query.limit, query.offset),
        ).fetchall()
    finally:
        connection.close()
    entries = [
        FileEntryInfo(
            name=str(row[0]),
            is_directory=bool(row[1]),
            size=int(row[2]),
            modified_at_ms=int(row[3]),
            mime_type=str(row[4]),
            type_id=classify_file_entry_type(
                str(row[0]),
                str(row[4]),
                is_directory=bool(row[1]),
            ),
            type_rank=int(row[5]),
            permissions=str(row[6]),
        )
        for row in rows
    ]
    next_offset = query.offset + len(entries)
    has_more = next_offset < total
    return DirectoryListingSnapshotPage(
        entries=entries,
        total=total,
        has_more=has_more,
        next_offset=next_offset if has_more else None,
    )


def locate_directory_listing_entry(
    query: DirectoryListingQuery,
    *,
    name: str,
) -> int:
    connection = connect_sqlite(
        query.snapshot_path,
        timeout=SQLITE_BUSY_TIMEOUT_SECONDS,
        must_exist=True,
    )
    try:
        where_clause = _where_clause(query.entry_type)
        row = connection.execute(
            (
                "SELECT listing_offset FROM ("
                "SELECT name, ROW_NUMBER() OVER ("
                f"{_order_clause(query.sort_column, query.sort_direction)}"
                ") - 1 AS listing_offset"
                f" FROM entries{where_clause}"
                ") WHERE name = ?"
                " ORDER BY listing_offset ASC LIMIT 1"
            ),
            (name,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise FileNotFoundError(name)
    return int(row[0])

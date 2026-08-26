"""SoAI - File explorer list/search response serialization [backend/features/api/routes/file_explorer/listing_serialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.explorer_models import (
    FileEntryInfo,
    ListDirectoryResult,
    SearchResult,
    SearchResultEntry,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "serialize_file_entry",
    "serialize_list_result",
    "serialize_search_result",
)


def serialize_file_entry(entry: FileEntryInfo | SearchResultEntry) -> JSONDict:
    return {
        "name": entry.name,
        "is_directory": entry.is_directory,
        "size": entry.size,
        "modified_at_ms": entry.modified_at_ms,
        "mime_type": entry.mime_type,
        "type_id": entry.type_id,
        "type_rank": entry.type_rank,
        "permissions": entry.permissions,
    }


def serialize_list_result(result: ListDirectoryResult) -> JSONDict:
    entries = [serialize_file_entry(entry) for entry in result.entries]
    payload: JSONDict = {
        "path": result.path,
        "entries": entries,
        "total": result.total,
        "offset": result.offset,
        "limit": result.limit,
    }
    return payload


def serialize_search_result(result: SearchResult) -> JSONDict:
    entries: list[JSONDict] = []
    for entry in result.entries:
        serialized = serialize_file_entry(entry)
        serialized["path"] = entry.path
        entries.append(serialized)
    payload: JSONDict = {
        "query": result.query,
        "search_root": result.search_root,
        "entries": entries,
        "total": result.total,
        "offset": result.offset,
        "limit": result.limit,
        "truncated": result.truncated,
        "scanned_entries": result.scanned_entries,
    }
    return payload

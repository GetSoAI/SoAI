"""SoAI - MCP utility tools: list_dir, glob_files [backend/mcp/tools/file_listing_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from typing import TYPE_CHECKING

from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.files_access import get_workspace_context, resolve_existing_dir
from mcp.tools.glob_files_patterns import build_normalized_patterns_to_try
from mcp.tools.glob_files_sorting import collect_glob_matches_sorted
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "tool_glob_files",
    "tool_list_dir",
)

_DEFAULT_LIST_OFFSET: int = 1
_DEFAULT_LIST_LIMIT: int = 25
_DEFAULT_LIST_DEPTH: int = 2
_MAX_LIST_LIMIT: int = 2000
_MAX_LIST_DEPTH: int = 20

_DEFAULT_GLOB_LIMIT: int = 250
_MAX_GLOB_LIMIT: int = 5000
_DEFAULT_GLOB_SORT: str = "modified_desc"
_ALLOWED_LIST_DIR_KEYS: frozenset[str] = frozenset({"path", "offset", "limit", "depth"})
_ALLOWED_GLOB_FILES_KEYS: frozenset[str] = frozenset({"pattern", "path", "limit", "sort"})


def _iter_dir_entries(root_dir: str, *, depth: int) -> Iterator[tuple[str, str]]:
    def visit(current_dir: str, current_depth: int) -> Iterator[tuple[str, str]]:
        if current_depth > depth:
            return
        with os.scandir(current_dir) as it:
            entries = sorted(it, key=lambda entry: entry.name)
        for entry in entries:
            entry_path = entry.path
            is_dir = entry.is_dir(follow_symlinks=False)
            yield (entry_path, "directory" if is_dir else "file")
            if is_dir and current_depth < depth:
                yield from visit(entry_path, current_depth + 1)

    yield from visit(root_dir, 1)


def _collect_dir_entries_page(
    *,
    root_dir: str,
    depth: int,
    offset: int,
    limit: int,
) -> tuple[list[tuple[str, str]], int | None, bool]:
    start_index = max(1, offset)
    stop_index_exclusive = start_index + max(1, limit)
    page: list[tuple[str, str]] = []
    scanned_entries = 0
    has_more = False
    for entry in _iter_dir_entries(root_dir, depth=depth):
        scanned_entries += 1
        if scanned_entries < start_index:
            continue
        if scanned_entries < stop_index_exclusive:
            page.append(entry)
            continue
        has_more = True
        break
    total_entries = None if has_more else scanned_entries
    return page, total_entries, has_more


async def tool_list_dir(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_LIST_DIR_KEYS)
    _, _state, workspace_path = get_workspace_context(utility_tools)
    path_value = arguments.get("path")
    if path_value is not None and not isinstance(path_value, str):
        raise MCPToolError(-32602, "Path must be a string")
    normalized_path = path_value.strip() if isinstance(path_value, str) else ""
    if not normalized_path:
        resolved_dir = workspace_path
    else:
        resolved_dir = resolve_existing_dir(
            utility_tools,
            normalized_path,
            description="path",
        )

    offset = parse_int(
        arguments.get("offset"),
        default=_DEFAULT_LIST_OFFSET,
        min_value=1,
        max_value=10_000_000,
    )
    limit = parse_int(
        arguments.get("limit"),
        default=_DEFAULT_LIST_LIMIT,
        min_value=1,
        max_value=_MAX_LIST_LIMIT,
    )
    depth = parse_int(
        arguments.get("depth"),
        default=_DEFAULT_LIST_DEPTH,
        min_value=1,
        max_value=_MAX_LIST_DEPTH,
    )

    page, total_entries, has_more = await asyncio.to_thread(
        _collect_dir_entries_page,
        root_dir=resolved_dir,
        depth=depth,
        offset=offset,
        limit=limit,
    )
    next_offset = offset + len(page) if has_more else None

    return {
        "path": resolved_dir,
        "offset": offset,
        "limit": limit,
        "depth": depth,
        "total_entries": total_entries,
        "truncated": has_more,
        "has_more": has_more,
        "next_offset": next_offset,
        "entries": [{"path": path, "type": entry_type} for path, entry_type in page],
    }


async def tool_glob_files(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_GLOB_FILES_KEYS)
    pattern = get_arg(arguments, "pattern")
    if not isinstance(pattern, str) or not pattern.strip():
        raise MCPToolError(-32602, "Pattern must be a non-empty string")
    normalized_pattern = pattern.strip()
    patterns_to_try = build_normalized_patterns_to_try(normalized_pattern)

    _, _state, workspace_path = get_workspace_context(utility_tools)
    root_dir = workspace_path
    path_value = arguments.get("path")
    if path_value is not None and not isinstance(path_value, str):
        raise MCPToolError(-32602, "Path must be a string")
    if isinstance(path_value, str) and path_value.strip():
        root_dir = resolve_existing_dir(utility_tools, path_value.strip(), description="path")

    limit = parse_int(
        arguments.get("limit"),
        default=_DEFAULT_GLOB_LIMIT,
        min_value=1,
        max_value=_MAX_GLOB_LIMIT,
    )

    sort_value = arguments.get("sort")
    if sort_value is None:
        normalized_sort = _DEFAULT_GLOB_SORT
    else:
        if not isinstance(sort_value, str):
            raise MCPToolError(-32602, "Sort must be a string")
        normalized_sort = sort_value.strip() or _DEFAULT_GLOB_SORT

    try:
        search_result = await asyncio.to_thread(
            collect_glob_matches_sorted,
            root_dir=root_dir,
            patterns_to_try=patterns_to_try,
            limit=limit,
            sort=normalized_sort,
        )
    except ValueError as exception:
        raise MCPToolError(-32602, str(exception)) from exception

    truncated = search_result.total_matches > limit
    return {
        "pattern": normalized_pattern,
        "path": root_dir,
        "limit": limit,
        "sort": normalized_sort,
        "total_matches": search_result.total_matches,
        "truncated": truncated,
        "matches": search_result.matches,
    }

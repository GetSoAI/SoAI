"""SoAI - MCP utility tool: grep_files [backend/mcp/tools/file_grep_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import re
from typing import TYPE_CHECKING

from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.validation.booleans import parse_bool_flag_with_default
from mcp.tools.argument_fields import (
    normalize_string_argument,
    require_non_empty_string,
)
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError
from mcp.tools.files_access import (
    get_workspace_context,
    normalize_str,
    resolve_workspace_path,
)
from mcp.tools.grep_ripgrep_runner import run_ripgrep
from mcp.tools.grep_types import (
    DEFAULT_PER_FILE_COUNT,
    DEFAULT_SEARCH_LIMIT,
    FILE_TYPE_VALID_PATTERN,
    MAX_CONTEXT_LINES,
    MAX_PER_FILE_COUNT,
    MAX_SEARCH_LIMIT,
    GrepFileMatch,
    GrepRequest,
    GrepResult,
)
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_grep_files",)

_VALID_OUTPUT_MODES: frozenset[str] = frozenset(("content", "files_with_matches", "count"))


def _parse_output_mode(arguments: JSONDict) -> str:
    normalized = normalize_string_argument(
        arguments.get("output_mode"),
        field="output_mode",
        required=False,
    )
    if normalized is None:
        return "files_with_matches"
    if normalized not in _VALID_OUTPUT_MODES:
        raise MCPToolError(-32602, "output_mode must be one of content, files_with_matches, count")
    if normalized == "content":
        return "content"
    if normalized == "files_with_matches":
        return "files_with_matches"
    return "count"


def _parse_context_fields(arguments: JSONDict, mode: str) -> tuple[int, int]:
    before_raw = arguments.get("before_context")
    after_raw = arguments.get("after_context")
    context_raw = arguments.get("context")
    any_present = before_raw is not None or after_raw is not None or context_raw is not None
    if any_present and mode != "content":
        raise MCPToolError(
            -32602,
            "before_context/after_context/context only allowed in content mode",
        )
    context = parse_int(context_raw, default=0, min_value=0, max_value=MAX_CONTEXT_LINES)
    before = parse_int(before_raw, default=0, min_value=0, max_value=MAX_CONTEXT_LINES)
    after = parse_int(after_raw, default=0, min_value=0, max_value=MAX_CONTEXT_LINES)
    if context > 0:
        if before == 0:
            before = context
        if after == 0:
            after = context
    return before, after


def _parse_max_count(arguments: JSONDict, mode: str) -> int:
    raw = arguments.get("max_count_per_file")
    if raw is not None and mode != "content":
        raise MCPToolError(-32602, "max_count_per_file only allowed in content mode")
    return parse_int(
        raw,
        default=DEFAULT_PER_FILE_COUNT,
        min_value=1,
        max_value=MAX_PER_FILE_COUNT,
    )


def _parse_file_type(arguments: JSONDict) -> str | None:
    stripped = normalize_string_argument(
        arguments.get("file_type"),
        field="file_type",
        required=False,
    )
    if not stripped:
        return None
    if not re.match(FILE_TYPE_VALID_PATTERN, stripped):
        raise MCPToolError(
            -32602,
            "file_type must match ^[a-zA-Z0-9_+-]{1,16}$ (e.g. 'py', 'ts', 'rs')",
        )
    return stripped


def _parse_multiline(arguments: JSONDict, mode: str) -> bool:
    raw = arguments.get("multiline")
    if raw is not None and mode != "content":
        raise MCPToolError(-32602, "multiline only allowed in content mode")
    return parse_bool_flag_with_default(raw, default=False)


def _resolve_search_target(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> tuple[str, str, str | None, bool]:
    _, _state, workspace_path = get_workspace_context(utility_tools)
    search_root = workspace_path
    root_for_rel = search_root
    candidate_file: str | None = None
    path_value = normalize_str(arguments.get("path"), field="path", required=False)
    explicit_path = bool(path_value)
    if path_value:
        resolved = resolve_workspace_path(utility_tools, path_value, description="path")
        if os.path.isdir(resolved):
            search_root = resolved
            root_for_rel = resolved
        elif os.path.isfile(resolved):
            search_root = resolved
            candidate_file = resolved
            root_for_rel = os.path.dirname(resolved)
        else:
            raise MCPToolError(-32602, f"path not found: {path_value}")
    apply_defaults = candidate_file is None and not explicit_path and search_root == workspace_path
    return search_root, root_for_rel, candidate_file, apply_defaults


def _require_pattern(arguments: JSONDict) -> str:
    if "pattern" not in arguments:
        raise MCPToolError(-32602, "Missing required parameter: pattern")
    return require_non_empty_string(arguments["pattern"], key="pattern")


def _build_request(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> GrepRequest:
    pattern = _require_pattern(arguments)
    mode = _parse_output_mode(arguments)
    before, after = _parse_context_fields(arguments, mode)
    max_count = _parse_max_count(arguments, mode)
    file_type = _parse_file_type(arguments)
    multiline = _parse_multiline(arguments, mode)
    include = normalize_str(arguments.get("include"), field="include", required=False)
    head_limit = parse_int(
        arguments.get("head_limit"),
        default=DEFAULT_SEARCH_LIMIT,
        min_value=1,
        max_value=MAX_SEARCH_LIMIT,
    )
    offset = parse_int(arguments.get("offset"), default=0, min_value=0, max_value=MAX_SEARCH_LIMIT)
    case_insensitive = parse_bool_flag_with_default(
        arguments.get("case_insensitive"),
        default=False,
    )
    search_root, root_for_rel, candidate_file, apply_defaults = _resolve_search_target(
        utility_tools,
        arguments,
    )
    return GrepRequest(
        pattern=pattern,
        include=include,
        search_root=search_root,
        root_for_rel=root_for_rel,
        candidate_file=candidate_file,
        output_mode=mode,
        case_insensitive=case_insensitive,
        multiline=multiline,
        file_type=file_type,
        before_context=before,
        after_context=after,
        head_limit=head_limit,
        offset=offset,
        max_count_per_file=max_count,
        apply_default_excludes=apply_defaults,
    )


def _serialize_file(entry: GrepFileMatch) -> JSONDict:
    lines: list[JSONValue] = [
        {
            "line_number": hit.line_number,
            "text": hit.text,
            "is_context": hit.is_context,
        }
        for hit in entry.lines
    ]
    payload: JSONDict = {"path": entry.path, "match_count": entry.match_count, "lines": lines}
    return payload


def _serialize_result(request: GrepRequest, result: GrepResult) -> JSONDict:
    files_payload: list[JSONValue] = [_serialize_file(entry) for entry in result.files]
    payload: JSONDict = {
        "pattern": request.pattern,
        "output_mode": request.output_mode,
        "path": request.search_root,
        "head_limit": request.head_limit,
        "offset": request.offset,
        "truncated": result.truncated,
        "total_matches": result.total_matches,
        "files": files_payload,
    }
    include_value: JSONValue = request.include
    if include_value is not None:
        payload["include"] = include_value
    reason_value: JSONValue = result.truncated_reason
    if reason_value is not None:
        payload["truncated_reason"] = reason_value
    return payload


async def tool_grep_files(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    request = _build_request(utility_tools, arguments)
    try:
        result = await asyncio.wait_for(
            run_ripgrep(utility_tools.runtime_flags, request),
            timeout=INTERACTIVE_TIMEOUT_SEC,
        )
    except TimeoutError as exception:
        raise MCPToolError(
            -32603,
            (
                f"grep_files timed out after {int(INTERACTIVE_TIMEOUT_SEC)} seconds. "
                "Narrow the path or add include to reduce the search scope."
            ),
            data={"reason": "timeout", "retryable": True},
        ) from exception
    return _serialize_result(request, result)

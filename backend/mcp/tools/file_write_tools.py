"""SoAI - MCP utility tools: write_file, replace_in_file [backend/mcp/tools/file_write_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.validation.booleans import parse_bool_flag_with_default
from mcp.tools.argument_fields import require_non_empty_string, require_string
from mcp.tools.argument_scalars import parse_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.file_guard import record_file_written, require_fresh_read
from mcp.tools.file_replace_operation import execute_replace_in_file_io
from mcp.tools.file_write_operation import execute_write_file_io
from mcp.tools.files_access import resolve_existing_file, resolve_workspace_path

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
    from mcp.tools.runtime_types import FileSignature

__all__ = (
    "tool_replace_in_file",
    "tool_write_file",
)


async def tool_write_file(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    file_path = get_arg(arguments, "file_path")
    content = get_arg(arguments, "content")
    file_path = require_non_empty_string(
        file_path,
        key="file_path",
        type_message="file_path must be a non-empty string",
        empty_message="file_path must be a non-empty string",
    )
    content = require_string(content, key="content", type_message="content must be a string")

    overwrite = parse_bool_flag_with_default(arguments.get("overwrite"), default=False)
    dry_run = parse_bool_flag_with_default(arguments.get("dry_run"), default=False)
    resolved_path = resolve_workspace_path(utility_tools, file_path, description="file_path")
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    files_state = utility_tools.runtime_sessions.get_or_create_workspace_state(owner_key)
    expected_signature: FileSignature | None = None
    if overwrite and os.path.isfile(resolved_path):
        stamp = require_fresh_read(
            utility_tools,
            files_state,
            resolved_path,
            file_label=file_path.strip(),
        )
        if stamp is not None:
            expected_signature = stamp.signature

    existed_before, changed, committed, code_diffs = await asyncio.to_thread(
        execute_write_file_io,
        resolved_path,
        file_path.strip(),
        content,
        overwrite,
        dry_run,
        expected_signature,
        utility_tools.storage_manager,
    )
    if committed and os.path.isfile(resolved_path):
        record_file_written(files_state, resolved_path)
    byte_count = len(content.encode("utf-8", errors="replace"))
    return {
        "path": resolved_path,
        "bytes": byte_count,
        "existed_before": existed_before,
        "changed": changed,
        "committed": committed,
        "dry_run": dry_run,
        "code_diffs": code_diffs,
    }


async def tool_replace_in_file(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    file_path = get_arg(arguments, "file_path")
    find_text = get_arg(arguments, "find")
    replace_text = get_arg(arguments, "replace")
    file_path = require_non_empty_string(
        file_path,
        key="file_path",
        type_message="file_path must be a non-empty string",
        empty_message="file_path must be a non-empty string",
    )
    find_text = require_string(find_text, key="find", type_message="find must be a string")
    replace_text = require_string(
        replace_text,
        key="replace",
        type_message="replace must be a string",
    )
    if not find_text:
        raise MCPToolError(-32602, "Find must be non-empty")

    replace_all = parse_bool_flag_with_default(arguments.get("replace_all"), default=False)
    allow_noop = parse_bool_flag_with_default(arguments.get("allow_noop"), default=False)
    dry_run = parse_bool_flag_with_default(arguments.get("dry_run"), default=False)

    expected_raw = arguments.get("expected_replacements")
    expected: int | None = None
    if expected_raw is not None:
        expected_parsed = parse_int(
            expected_raw,
            default=-1,
            min_value=-10_000_000,
            max_value=10_000_000,
        )
        if expected_parsed < 0:
            raise MCPToolError(-32602, "Expected_replacements must be a non-negative integer")
        expected = expected_parsed

    resolved_path = resolve_existing_file(utility_tools, file_path, description="file_path")
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    files_state = utility_tools.runtime_sessions.get_or_create_workspace_state(owner_key)
    expected_signature: FileSignature | None = None
    stamp = require_fresh_read(
        utility_tools,
        files_state,
        resolved_path,
        file_label=file_path.strip(),
    )
    if stamp is not None:
        expected_signature = stamp.signature

    replacements, changed, committed, code_diffs = await asyncio.to_thread(
        execute_replace_in_file_io,
        resolved_path,
        file_path.strip(),
        find_text,
        replace_text,
        replace_all,
        allow_noop,
        dry_run,
        expected,
        expected_signature,
        utility_tools.storage_manager,
    )
    if committed and os.path.isfile(resolved_path):
        record_file_written(files_state, resolved_path)
    return {
        "path": resolved_path,
        "replacements": replacements,
        "changed": changed,
        "committed": committed,
        "dry_run": dry_run,
        "code_diffs": code_diffs,
    }

"""SoAI - MCP replace_in_file disk operation [backend/mcp/tools/file_replace_operation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError
from mcp.tools.file_write_common import (
    build_updated_text_file_diffs,
    commit_reserved_text_update,
    read_mcp_text_file,
    verify_existing_file_signature,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict
    from mcp.tools.runtime_types import FileSignature

__all__ = ("execute_replace_in_file_io",)


def execute_replace_in_file_io(
    resolved_path: str,
    file_path_label: str,
    find_text: str,
    replace_text: str,
    replace_all: bool,
    allow_noop: bool,
    dry_run: bool,
    expected: int | None,
    expected_signature: FileSignature | None,
    storage_manager: StorageManagerProtocol,
) -> tuple[int, bool, bool, list[JSONDict]]:
    verify_existing_file_signature(
        resolved_path,
        file_path_label=file_path_label,
        expected_signature=expected_signature,
    )
    original = _read_replace_source(resolved_path, file_path_label)
    verify_existing_file_signature(
        resolved_path,
        file_path_label=file_path_label,
        expected_signature=expected_signature,
    )
    count = _validate_replacement_count(
        original,
        find_text,
        expected=expected,
        replace_all=replace_all,
        allow_noop=allow_noop,
        file_path_label=file_path_label,
    )
    if count == 0:
        verify_existing_file_signature(
            resolved_path,
            file_path_label=file_path_label,
            expected_signature=expected_signature,
        )
        return (0, False, False, [])
    updated = original.replace(find_text, replace_text)
    code_diffs = _build_replace_diffs(file_path_label, original, updated)
    changed = bool(code_diffs)
    if dry_run or not changed:
        verify_existing_file_signature(
            resolved_path,
            file_path_label=file_path_label,
            expected_signature=expected_signature,
        )
        return (count, changed, False, code_diffs)
    commit_reserved_text_update(
        storage_manager=storage_manager,
        path=resolved_path,
        file_path_label=file_path_label,
        content=updated,
        expected_signature=expected_signature,
        operation="mcp.tools.replace_in_file.update",
    )
    return (count, True, True, code_diffs)


def _read_replace_source(resolved_path: str, file_path_label: str) -> str:
    try:
        return read_mcp_text_file(resolved_path, file_path_label, errors="strict")
    except UnicodeDecodeError as exception:
        raise MCPToolError(
            -32602,
            f"file is not valid utf-8 text and cannot be edited with replace_in_file: {file_path_label}",
        ) from exception


def _validate_replacement_count(
    original: str,
    find_text: str,
    *,
    expected: int | None,
    replace_all: bool,
    allow_noop: bool,
    file_path_label: str,
) -> int:
    count = original.count(find_text)
    if expected is not None and count != expected:
        raise MCPToolError(
            -32602,
            f"expected_replacements mismatch: expected {expected}, found {count}",
        )
    if count > 1 and expected is None and not replace_all:
        raise MCPToolError(
            -32602,
            "ambiguous match: multiple occurrences found; set replace_all=true or expected_replacements",
        )
    if count == 0 and expected is None and not allow_noop:
        raise MCPToolError(
            -32602,
            f"no matches for find in file; set allow_noop=true to permit a no-op: {file_path_label}",
        )
    return count


def _build_replace_diffs(file_path_label: str, original: str, updated: str) -> list[JSONDict]:
    return build_updated_text_file_diffs(
        file_path_label=file_path_label,
        old_content=original,
        new_content=updated,
    )

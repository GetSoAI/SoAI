"""SoAI - MCP write_file disk operation [backend/mcp/tools/file_write_operation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.files.code_diffs import build_added_file_diff
from core.hardware.reservation_claims import claim_reserved_write
from mcp.tools.error import MCPToolError
from mcp.tools.file_write_common import (
    build_updated_text_file_diffs,
    commit_reserved_text_update,
    read_mcp_text_file,
    reserve_text_write_bytes,
    verify_existing_file_signature,
    write_text_file_exclusive,
)

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict
    from mcp.tools.runtime_types import FileSignature

__all__ = ("execute_write_file_io",)


def execute_write_file_io(
    resolved_path: str,
    file_path_label: str,
    content: str,
    overwrite: bool,
    dry_run: bool,
    expected_signature: FileSignature | None,
    storage_manager: StorageManagerProtocol,
) -> tuple[bool, bool, bool, list[JSONDict]]:
    if os.path.isdir(resolved_path):
        raise MCPToolError(-32602, f"Path is a directory: {file_path_label}")
    existed_before = os.path.exists(resolved_path)
    if existed_before and not overwrite:
        raise MCPToolError(-32602, f"File exists and overwrite is false: {file_path_label}")
    if existed_before:
        verify_existing_file_signature(
            resolved_path,
            file_path_label=file_path_label,
            expected_signature=expected_signature,
        )
    existing_content = _read_existing_content(resolved_path, file_path_label, existed_before)
    if existed_before:
        verify_existing_file_signature(
            resolved_path,
            file_path_label=file_path_label,
            expected_signature=expected_signature,
        )
    code_diffs = _build_write_diffs(
        existed_before=existed_before,
        file_path_label=file_path_label,
        existing_content=existing_content,
        content=content,
    )
    changed = (not existed_before) or bool(code_diffs)
    committed = False
    if not dry_run and changed:
        if existed_before:
            commit_reserved_text_update(
                storage_manager=storage_manager,
                path=resolved_path,
                file_path_label=file_path_label,
                content=content,
                expected_signature=expected_signature,
                operation="mcp.tools.write_file.update",
            )
        else:
            _commit_new_file_write(resolved_path, file_path_label, content, storage_manager)
        committed = True
    if dry_run and existed_before:
        verify_existing_file_signature(
            resolved_path,
            file_path_label=file_path_label,
            expected_signature=expected_signature,
        )
    return (existed_before, changed, committed, code_diffs)


def _read_existing_content(resolved_path: str, file_path_label: str, existed_before: bool) -> str:
    if not existed_before:
        return ""
    return read_mcp_text_file(resolved_path, file_path_label, errors="replace")


def _build_write_diffs(
    *,
    existed_before: bool,
    file_path_label: str,
    existing_content: str,
    content: str,
) -> list[JSONDict]:
    code_diffs: list[JSONDict] = []
    if existed_before:
        return build_updated_text_file_diffs(
            file_path_label=file_path_label,
            old_content=existing_content,
            new_content=content,
        )
    diff = build_added_file_diff(path=file_path_label, new_content=content)
    if diff is not None:
        code_diffs.append(diff)
    return code_diffs


def _commit_new_file_write(
    resolved_path: str,
    file_path_label: str,
    content: str,
    storage_manager: StorageManagerProtocol,
) -> None:
    with reserve_text_write_bytes(
        storage_manager,
        path=resolved_path,
        file_path_label=file_path_label,
        content=content,
        operation="mcp.tools.write_file.create",
    ) as reservation:
        with claim_reserved_write(
            reservation,
            size_bytes=len(content.encode("utf-8", errors="replace")),
        ):
            write_text_file_exclusive(resolved_path, content, file_path_label=file_path_label)

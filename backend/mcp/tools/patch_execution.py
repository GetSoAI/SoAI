"""SoAI - MCP apply_patch operation execution and diff output [backend/mcp/tools/patch_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError
from core.files.code_diffs import (
    build_added_file_diff,
    build_deleted_file_diff,
    build_updated_file_diff,
)
from core.files.protected_sqlite_runtime_paths import ensure_not_protected_sqlite_runtime_file
from core.filesystem.atomic_writes import (
    atomic_create_text_content_exclusive,
    atomic_write_text_content,
)
from core.hardware.reservation_claims import claim_reserved_write
from core.meta.paths import get_database_path, get_project_root
from mcp.tools.error import MCPToolError
from mcp.tools.file_signatures import signature_for_existing_file
from mcp.tools.patch_reservations import encoded_text_size_bytes
from mcp.tools.patch_types import AddOperation, DeleteOperation, UpdateOperation
from mcp.tools.runtime_types import FileSignature

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict

__all__ = ("apply_patch_operations",)


def _verify_expected_signature(
    path: str,
    *,
    file_label: str,
    expected_signatures: dict[str, FileSignature] | None,
) -> None:
    if expected_signatures is None:
        return
    expected = expected_signatures.get(path)
    if expected is None:
        return
    current = signature_for_existing_file(path, file_label=file_label)
    if current != expected:
        raise MCPToolError(
            -32602,
            f"File has been modified since it was last read; read it again before editing it: {file_label}",
        )


def apply_patch_operations(
    operations: list[AddOperation | DeleteOperation | UpdateOperation],
    *,
    expected_signatures: dict[str, FileSignature] | None = None,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> tuple[list[str], list[str], list[str], list[JSONDict], list[JSONDict]]:
    added: list[str] = []
    updated: list[str] = []
    deleted: list[str] = []
    moved: list[JSONDict] = []
    code_diffs: list[JSONDict] = []
    for operation in operations:
        match operation:
            case AddOperation():
                _ensure_patch_target_is_mutable(operation.target_path)
                try:
                    with claim_reserved_write(
                        write_reservation,
                        size_bytes=encoded_text_size_bytes(operation.content_text),
                    ):
                        atomic_create_text_content_exclusive(
                            operation.target_path,
                            operation.content_text,
                            errors="replace",
                        )
                except OSError as os_exception:
                    raise MCPToolError(
                        -32602,
                        f"Failed to add file {operation.rel_path}: {os_exception}",
                    ) from os_exception
                added.append(operation.target_path)
                code_diff = build_added_file_diff(
                    path=operation.rel_path,
                    new_content=operation.content_text,
                )
                if code_diff is not None:
                    code_diffs.append(code_diff)
            case DeleteOperation():
                _ensure_patch_target_is_mutable(operation.target_path)
                _verify_expected_signature(
                    operation.target_path,
                    file_label=operation.rel_path,
                    expected_signatures=expected_signatures,
                )
                try:
                    os.remove(operation.target_path)
                except OSError as os_exception:
                    raise MCPToolError(
                        -32602,
                        f"Failed to delete file {operation.rel_path}: {os_exception}",
                    ) from os_exception
                deleted.append(operation.target_path)
                code_diff = build_deleted_file_diff(
                    path=operation.rel_path,
                    old_content=operation.deleted_content,
                )
                if code_diff is not None:
                    code_diffs.append(code_diff)
                if expected_signatures is not None:
                    expected_signatures.pop(operation.target_path, None)
            case UpdateOperation():
                _ensure_patch_target_is_mutable(operation.source_path)
                _ensure_patch_target_is_mutable(operation.dest_path)
                _verify_expected_signature(
                    operation.source_path,
                    file_label=operation.rel_path,
                    expected_signatures=expected_signatures,
                )
                try:
                    with claim_reserved_write(
                        write_reservation,
                        size_bytes=encoded_text_size_bytes(operation.updated_text),
                    ):
                        atomic_write_text_content(
                            operation.dest_path,
                            operation.updated_text,
                            errors="replace",
                        )
                        if operation.dest_path != operation.source_path:
                            os.remove(operation.source_path)
                except OSError as os_exception:
                    raise MCPToolError(
                        -32602,
                        f"Failed to update file {operation.rel_path}: {os_exception}",
                    ) from os_exception
                updated.append(operation.dest_path)
                if operation.dest_path != operation.source_path:
                    moved.append({"from": operation.source_path, "to": operation.dest_path})
                code_diff = build_updated_file_diff(
                    path=operation.diff_path,
                    old_content=operation.original_text,
                    new_content=operation.updated_text,
                )
                if code_diff is not None:
                    code_diffs.append(code_diff)
                if expected_signatures is not None:
                    expected_signatures[operation.dest_path] = signature_for_existing_file(
                        operation.dest_path,
                        file_label=operation.dest_path,
                    )
                    if operation.dest_path != operation.source_path:
                        expected_signatures.pop(operation.source_path, None)
    return added, updated, deleted, moved, code_diffs


def _ensure_patch_target_is_mutable(path: str) -> None:
    try:
        ensure_not_protected_sqlite_runtime_file(
            path,
            get_database_path(get_project_root()),
            operation="mcp.patch_execution",
        )
    except SecurityError as exception:
        raise MCPToolError(
            -32602,
            "Refusing to mutate live SQLite runtime file.",
        ) from exception

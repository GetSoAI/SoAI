"""SoAI - MCP file write shared disk safeguards [backend/mcp/tools/file_write_common.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import InsufficientDiskSpaceError
from core.files.code_diffs import build_updated_file_diff
from core.filesystem.atomic_writes import (
    atomic_create_text_content_exclusive,
    atomic_write_text_content,
)
from core.filesystem.open_files import open_text
from core.hardware.reservation_claims import claim_reserved_write
from mcp.tools.error import MCPToolError
from mcp.tools.file_signatures import signature_for_existing_file

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )
    from core.types.json import JSONDict
    from mcp.tools.runtime_types import FileSignature

__all__ = (
    "build_updated_text_file_diffs",
    "commit_reserved_text_update",
    "read_mcp_text_file",
    "reserve_text_write_bytes",
    "verify_existing_file_signature",
    "write_text_file_exclusive",
)


def commit_reserved_text_update(
    *,
    storage_manager: StorageManagerProtocol,
    path: str,
    file_path_label: str,
    content: str,
    expected_signature: FileSignature | None,
    operation: str,
) -> None:
    verify_existing_file_signature(
        path,
        file_path_label=file_path_label,
        expected_signature=expected_signature,
    )
    with reserve_text_write_bytes(
        storage_manager,
        path=path,
        file_path_label=file_path_label,
        content=content,
        operation=operation,
    ) as reservation:
        verify_existing_file_signature(
            path,
            file_path_label=file_path_label,
            expected_signature=expected_signature,
        )
        with claim_reserved_write(
            reservation,
            size_bytes=len(content.encode("utf-8", errors="replace")),
        ):
            try:
                atomic_write_text_content(path, content, errors="replace")
            except OSError as os_exception:
                raise MCPToolError(
                    -32602,
                    f"Failed to write file {file_path_label}: {os_exception}",
                ) from os_exception


def read_mcp_text_file(
    resolved_path: str,
    file_path_label: str,
    *,
    errors: str,
) -> str:
    try:
        with open_text(resolved_path, mode="r", encoding="utf-8", errors=errors) as file_handle:
            return file_handle.read()
    except OSError as os_exception:
        raise MCPToolError(
            -32602,
            f"Failed to read file {file_path_label}: {os_exception}",
        ) from os_exception


def build_updated_text_file_diffs(
    *,
    file_path_label: str,
    old_content: str,
    new_content: str,
) -> list[JSONDict]:
    code_diffs: list[JSONDict] = []
    diff = build_updated_file_diff(
        path=file_path_label,
        old_content=old_content,
        new_content=new_content,
    )
    if diff is not None:
        code_diffs.append(diff)
    return code_diffs


def verify_existing_file_signature(
    resolved_path: str,
    *,
    file_path_label: str,
    expected_signature: FileSignature | None,
) -> None:
    if expected_signature is None:
        return
    current_signature = signature_for_existing_file(resolved_path, file_label=file_path_label)
    if current_signature != expected_signature:
        raise MCPToolError(
            -32602,
            f"File has been modified since it was last read; read it again before editing it: {file_path_label}",
        )


def write_text_file_exclusive(path: str, content: str, *, file_path_label: str) -> None:
    try:
        atomic_create_text_content_exclusive(path, content, errors="replace")
    except FileExistsError as exception:
        raise MCPToolError(
            -32602,
            f"File exists and overwrite is false: {file_path_label}",
        ) from exception
    except OSError as os_exception:
        raise MCPToolError(
            -32602,
            f"Failed to write file {file_path_label}: {os_exception}",
        ) from os_exception


def reserve_text_write_bytes(
    storage_manager: StorageManagerProtocol,
    *,
    path: str,
    file_path_label: str,
    content: str,
    operation: str,
) -> DiskSpaceReservationLeaseProtocol:
    required_bytes = len(content.encode("utf-8", errors="replace"))
    try:
        return storage_manager.reserve_disk_space(
            path=path,
            required_bytes=required_bytes,
            operation=operation,
            details={
                "path": file_path_label,
                "required_bytes": required_bytes,
            },
        )
    except InsufficientDiskSpaceError as exception:
        raise MCPToolError(-32603, str(exception)) from exception

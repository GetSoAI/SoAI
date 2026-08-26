"""SoAI - MCP stable local file snapshot reads [backend/mcp/tools/file_stable_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.files.mime_detection import detect_mime_type
from core.filesystem.open_files import open_regular_binary_no_symlink
from mcp.tools.error import MCPToolError
from mcp.tools.files_access import resolve_existing_file
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.runtime_types import FileSignature

__all__ = ("StableFileSnapshot", "read_stable_file_snapshot")

_MIME_SAMPLE_BYTES: int = 8192


@dataclass(frozen=True, slots=True)
class StableFileSnapshot:
    resolved_path: str
    data: bytes
    source_size_bytes: int
    mime_sample: bytes
    detected_mime_type: str
    signature: FileSignature
    exceeded_max_bytes: bool


def _signature_from_stat(stat_result: os.stat_result) -> FileSignature:
    return FileSignature(
        dev=int(stat_result.st_dev),
        inode=int(stat_result.st_ino),
        mtime_ns=int(stat_result.st_mtime_ns),
        size_bytes=int(stat_result.st_size),
    )


def _stat_regular_path(path: str, *, file_label: str) -> os.stat_result:
    try:
        stat_result = os.stat(path)
    except OSError as exception:
        raise MCPToolError(-32602, f"Failed to stat file {file_label}: {exception}") from exception
    if not stat.S_ISREG(stat_result.st_mode):
        raise MCPToolError(-32602, f"File is not a file: {file_label}")
    return stat_result


def _require_matching_signature(
    expected: FileSignature,
    actual: FileSignature,
    *,
    file_label: str,
) -> None:
    if actual != expected:
        raise MCPToolError(
            -32602,
            f"file changed while reading; retry the read operation: {file_label}",
        )


def _require_valid_max_bytes(max_bytes: int) -> None:
    if max_bytes < 0:
        raise MCPToolError(-32602, "max_bytes must be greater than or equal to 0.")


def _resolve_workspace_file(
    utility_tools: MCPUtilityToolsProtocol,
    file_path: str,
    *,
    description: str,
) -> str:
    try:
        return resolve_existing_file(utility_tools, file_path, description=description)
    except MCPToolError as exception:
        raise MCPToolError(-32602, str(exception)) from exception


def read_stable_file_snapshot(
    utility_tools: MCPUtilityToolsProtocol,
    file_path: str,
    *,
    max_bytes: int,
    description: str = "file_path",
    sample_only_when_oversize: bool = False,
) -> StableFileSnapshot:
    _require_valid_max_bytes(max_bytes)
    resolved_path = _resolve_workspace_file(utility_tools, file_path, description=description)
    stat_before = _stat_regular_path(resolved_path, file_label=file_path)
    signature_before = _signature_from_stat(stat_before)
    try:
        with open_regular_binary_no_symlink(
            resolved_path,
            not_found_message=f"File not found: {file_path}",
            symlink_message=f"File must not be a symlink: {file_path}",
            open_message=f"Failed to open file: {file_path}",
            inspect_message=f"Failed to inspect file: {file_path}",
            regular_file_message=f"File is not a file: {file_path}",
        ) as file_handle:
            signature_opened = _signature_from_stat(os.fstat(file_handle.fileno()))
            _require_matching_signature(signature_before, signature_opened, file_label=file_path)
            read_limit = max_bytes + 1
            if sample_only_when_oversize and signature_opened.size_bytes > max_bytes:
                read_limit = _MIME_SAMPLE_BYTES
            data = file_handle.read(read_limit)
            signature_after_read = _signature_from_stat(os.fstat(file_handle.fileno()))
            _require_matching_signature(
                signature_before,
                signature_after_read,
                file_label=file_path,
            )
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    except OSError as exception:
        raise MCPToolError(-32602, f"Failed to read file {file_path}: {exception}") from exception
    stat_after = _stat_regular_path(resolved_path, file_label=file_path)
    signature_after = _signature_from_stat(stat_after)
    _require_matching_signature(signature_before, signature_after, file_label=file_path)
    mime_sample = data[:_MIME_SAMPLE_BYTES]
    detected_mime_type = (detect_mime_type(mime_sample, filename=resolved_path) or "").strip()
    exceeded_max_bytes = signature_after.size_bytes > max_bytes or len(data) > max_bytes
    return StableFileSnapshot(
        resolved_path=resolved_path,
        data=data,
        source_size_bytes=signature_after.size_bytes,
        mime_sample=mime_sample,
        detected_mime_type=detected_mime_type,
        signature=signature_after,
        exceeded_max_bytes=exceeded_max_bytes,
    )

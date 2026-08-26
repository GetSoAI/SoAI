"""SoAI - MCP file read-before-write guard [backend/mcp/tools/file_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.epoch import epoch_seconds_float
from core.timing.formatting import timestamp_to_utc_iso
from mcp.tools.error import MCPToolError
from mcp.tools.file_signatures import signature_for_existing_file
from mcp.tools.runtime_types import FileReadStamp, FileSignature, ToolWorkspaceState

if TYPE_CHECKING:
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "clear_file_stamp",
    "record_file_read",
    "record_file_read_with_signature",
    "record_file_written",
    "require_fresh_read",
)


def _guard_enabled(utility_tools: MCPUtilityToolsProtocol) -> bool:
    try:
        config = utility_tools.config
    except AttributeError:
        return False
    try:
        getter = config.get_bool
    except AttributeError:
        return False
    return bool(getter("TOOLS.MCP.FILE_GUARD_READ_BEFORE_WRITE.ENABLED"))


def _format_epoch_seconds(value: float | None) -> str:
    if value is None:
        return "unknown"
    try:
        return timestamp_to_utc_iso(value)
    except (OverflowError, OSError, ValueError):
        return "unknown"


def _format_mtime_ns(mtime_ns: int | None) -> str:
    if mtime_ns is None:
        return "unknown"
    seconds = mtime_ns / 1_000_000_000.0
    return _format_epoch_seconds(seconds)


def record_file_read(files_state: ToolWorkspaceState, path: str) -> FileReadStamp:
    return record_file_read_with_signature(
        files_state,
        path,
        signature_for_existing_file(path, file_label=path),
    )


def record_file_read_with_signature(
    files_state: ToolWorkspaceState,
    path: str,
    signature: FileSignature,
) -> FileReadStamp:
    stamp = FileReadStamp(signature=signature, read_at_epoch_sec=epoch_seconds_float())
    files_state.file_read_stamps[path] = stamp
    return stamp


def record_file_written(files_state: ToolWorkspaceState, path: str) -> FileReadStamp:
    return record_file_read(files_state, path)


def clear_file_stamp(files_state: ToolWorkspaceState, path: str) -> None:
    files_state.file_read_stamps.pop(path, None)


def require_fresh_read(
    utility_tools: MCPUtilityToolsProtocol,
    files_state: ToolWorkspaceState,
    path: str,
    *,
    file_label: str,
) -> FileReadStamp | None:
    if not _guard_enabled(utility_tools):
        return None
    stamp = files_state.file_read_stamps.get(path)
    if stamp is None:
        raise MCPToolError(
            -32602,
            f"you must read the file before editing it. file={file_label}. Use read_file for text files (render=raw recommended) or read_image for image files.",
        )
    current = signature_for_existing_file(path, file_label=file_label)
    expected = stamp.signature
    if current != expected:
        raise MCPToolError(
            -32602,
            f"File has been modified since it was last read; read it again before editing it. file={file_label}; current_mtime={_format_mtime_ns(current.mtime_ns)}; current_size={current.size_bytes}; last_read_mtime={_format_mtime_ns(expected.mtime_ns)}; last_read_size={expected.size_bytes}; last_read_at={_format_epoch_seconds(stamp.read_at_epoch_sec)}",
        )
    return stamp

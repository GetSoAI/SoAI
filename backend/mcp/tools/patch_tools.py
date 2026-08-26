"""SoAI - MCP utility tool: apply_patch [backend/mcp/tools/patch_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from mcp.tools.error import MCPToolError
from mcp.tools.file_guard import (
    clear_file_stamp,
    record_file_written,
    require_fresh_read,
)
from mcp.tools.files_paths import resolve_path_under_workspace
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.patch_execution import apply_patch_operations
from mcp.tools.patch_parsing import parse_patch_operations
from mcp.tools.patch_reservations import (
    reserve_patch_operation_writes,
    reserve_patch_rollback_snapshots,
)
from mcp.tools.patch_snapshots import (
    build_file_snapshots,
    collect_touched_paths,
    restore_file_snapshots,
)
from mcp.tools.runtime_types import FileSignature

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_apply_patch",)

_PATCH_BEGIN_LINE = "*** Begin Patch"
_PATCH_END_LINE = "*** End Patch"
_PATCH_NUMBERED_PREFIX_PATTERN = r"^(?:L\d+:\s|\d+:\s|\s*\d+\|)"
_PATCH_NUMBERED_PREFIX_CODEX_PATTERN = r"^L(\d+):\s(.*)$"
_PATCH_NUMBERED_PREFIX_COLON_PATTERN = r"^(\d+):\s(.*)$"
_PATCH_NUMBERED_PREFIX_PIPE_PATTERN = r"^\s*(\d+)\|(.*)$"


def _expect_non_empty(value: JSONValue, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MCPToolError(-32602, f"{field} must be a non-empty string")
    return value


def _strip_leading_blank_lines(lines: list[str]) -> list[str]:
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    return lines[index:] if index else lines


def _last_non_blank_line(lines: list[str]) -> str | None:
    for line in reversed(lines):
        if line.strip():
            return line
    return None


def _ensure_end_patch_is_final(patch_lines: list[str]) -> None:
    tail = _last_non_blank_line(patch_lines)
    if tail is None or tail.strip() != _PATCH_END_LINE:
        raise MCPToolError(
            -32602,
            "input must end with '*** End Patch' and contain no trailing content",
        )


def _parse_numbered_patch_prefix(line: str) -> tuple[str, int, str] | None:
    match = re.match(_PATCH_NUMBERED_PREFIX_CODEX_PATTERN, line)
    if match:
        return ("codex", int(match.group(1)), match.group(2))
    match = re.match(_PATCH_NUMBERED_PREFIX_COLON_PATTERN, line)
    if match:
        return ("colon", int(match.group(1)), match.group(2))
    match = re.match(_PATCH_NUMBERED_PREFIX_PIPE_PATTERN, line)
    if match:
        return ("pipe", int(match.group(1)), match.group(2))
    return None


def _normalize_numbered_patch_text(patch_text: str) -> str | None:
    trailing_newline = patch_text.endswith("\n")
    lines = patch_text.splitlines()
    trimmed = _strip_leading_blank_lines(lines)
    if trimmed and trimmed[0].strip() == _PATCH_BEGIN_LINE:
        normalized = "\n".join(trimmed)
        return normalized + ("\n" if trailing_newline else "")

    if not trimmed:
        return None
    first = trimmed[0]
    first_prefix = _parse_numbered_patch_prefix(first)
    if first_prefix is None:
        return None

    style, first_number, first_rest = first_prefix
    expected_number = first_number
    stripped: list[str] = [first_rest]
    for line in trimmed[1:]:
        if not line.strip():
            raise MCPToolError(-32602, "Numbered patch inputs must not contain blank lines.")
        prefix = _parse_numbered_patch_prefix(line)
        if prefix is None:
            raise MCPToolError(
                -32602,
                "Numbered patch inputs must prefix every non-blank line using a consistent style.",
            )
        line_style, number, rest = prefix
        if line_style != style:
            raise MCPToolError(
                -32602,
                "Numbered patch inputs must use a single prefix style for every line.",
            )
        expected_number += 1
        if number != expected_number:
            raise MCPToolError(
                -32602,
                "Numbered patch inputs must use consecutive line numbers with no gaps.",
            )
        stripped.append(rest)

    stripped_trimmed = _strip_leading_blank_lines(stripped)
    if not stripped_trimmed or stripped_trimmed[0].strip() != _PATCH_BEGIN_LINE:
        return None
    normalized = "\n".join(stripped_trimmed)
    return normalized + ("\n" if trailing_newline else "")


def _extract_existing_file_directives(patch_lines: list[str]) -> list[str]:
    ordered: dict[str, None] = {}
    for line in patch_lines:
        stripped = line.strip()
        if stripped == _PATCH_END_LINE:
            break
        if line.startswith("*** Update File: "):
            rel_path = line[len("*** Update File: ") :].strip()
            if rel_path:
                ordered[rel_path] = None
            continue
        if line.startswith("*** Delete File: "):
            rel_path = line[len("*** Delete File: ") :].strip()
            if rel_path:
                ordered[rel_path] = None
            continue
    return list(ordered.keys())


async def tool_apply_patch(utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    if "input" not in arguments:
        raise MCPToolError(-32602, "Missing required parameter: input")
    patch_input_value = arguments["input"]
    patch_text = _expect_non_empty(patch_input_value, field="input")
    patch_lines = _strip_leading_blank_lines(patch_text.splitlines())
    if not patch_lines or patch_lines[0].strip() != _PATCH_BEGIN_LINE:
        normalized = _normalize_numbered_patch_text(patch_text)
        if normalized is None:
            if patch_lines and re.match(_PATCH_NUMBERED_PREFIX_PATTERN, patch_lines[0]):
                raise MCPToolError(
                    -32602,
                    "input appears to be a numbered patch, but does not normalize into a valid patch; ensure every non-blank line is consistently prefixed and the stripped content starts with '*** Begin Patch'.",
                )
            raise MCPToolError(-32602, "input must start with '*** Begin Patch'")
        patch_text = normalized
        patch_lines = _strip_leading_blank_lines(patch_text.splitlines())
        if not patch_lines or patch_lines[0].strip() != _PATCH_BEGIN_LINE:
            raise MCPToolError(-32602, "input must start with '*** Begin Patch'")
    _ensure_end_patch_is_final(patch_lines)
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    files_state = utility_tools.runtime_sessions.get_or_create_workspace_state(owner_key)
    workspace_path = utility_tools.runtime_sessions.require_workspace_path(owner_key)
    expected_signatures: dict[str, FileSignature] = {}
    for rel_path in _extract_existing_file_directives(patch_lines):
        try:
            resolved = resolve_path_under_workspace(
                rel_path,
                workspace_path=workspace_path,
                description="file",
            )
        except ValidationError as exception:
            raise MCPToolError(-32602, str(exception)) from exception
        stamp = require_fresh_read(
            utility_tools,
            files_state,
            resolved,
            file_label=rel_path,
        )
        if stamp is not None:
            expected_signatures[resolved] = stamp.signature
    operations = parse_patch_operations(
        patch_lines,
        workspace_path=workspace_path,
    )
    touched_paths = collect_touched_paths(operations)
    try:
        snapshots = build_file_snapshots(touched_paths)
    except ValidationError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None
    rollback_reservation: DiskSpaceReservationLeaseProtocol | None = None
    reservations_ready = False
    try:
        write_reservation = reserve_patch_operation_writes(
            utility_tools.storage_manager,
            operations,
        )
        rollback_reservation = reserve_patch_rollback_snapshots(
            utility_tools.storage_manager,
            snapshots,
        )
        reservations_ready = True
    finally:
        if not reservations_ready and write_reservation is not None:
            write_reservation.release()
    try:
        added, updated, deleted, moved, code_diffs = apply_patch_operations(
            operations,
            expected_signatures=expected_signatures or None,
            write_reservation=write_reservation,
        )
    except MCPToolError as exception:
        restore_errors = restore_file_snapshots(
            snapshots,
            rollback_reservation=rollback_reservation,
        )
        if restore_errors:
            restore_message = "; ".join(restore_errors)
            raise MCPToolError(
                exception.rpc_code,
                f"{exception.message} Rollback failed: {restore_message}",
                exception.data,
            ) from exception
        raise
    finally:
        if write_reservation is not None:
            write_reservation.release()
        if rollback_reservation is not None:
            rollback_reservation.release()
    moved_from: set[str] = set()
    moved_to: set[str] = set()
    for entry in moved:
        from_path = entry.get("from")
        if isinstance(from_path, str) and from_path:
            moved_from.add(from_path)
        to_path = entry.get("to")
        if isinstance(to_path, str) and to_path:
            moved_to.add(to_path)

    for path in deleted:
        clear_file_stamp(files_state, path)
    for path in moved_from:
        clear_file_stamp(files_state, path)

    deleted_set = set(deleted)
    written_paths = (set(added) | set(updated) | moved_to) - deleted_set - moved_from
    for path in written_paths:
        record_file_written(files_state, path)
    return {
        "status": "ok",
        "added": added,
        "updated": updated,
        "deleted": deleted,
        "moved": moved,
        "code_diffs": code_diffs,
    }

"""SoAI - MCP apply_patch parsing and in-memory patch state [backend/mcp/tools/patch_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re

from core.filesystem.open_files import open_text
from mcp.tools.error import MCPToolError
from mcp.tools.files_paths import resolve_path_under_workspace_or_tool_error
from mcp.tools.patch_types import AddOperation, DeleteOperation, UpdateOperation

__all__ = ("parse_patch_operations",)


def _parse_update_hunks(patch_lines: list[str]) -> list[list[tuple[str, str]]]:
    hunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for line in patch_lines:
        if line.startswith("@@"):
            if current:
                hunks.append(current)
                current = []
            continue
        if line.strip() == "*** End of File":
            continue
        if not line:
            raise MCPToolError(-32602, "Invalid empty patch line in update section.")
        prefix = line[0]
        if prefix not in {" ", "+", "-"}:
            raise MCPToolError(-32602, f"Invalid patch line prefix: {prefix}")
        current.append((prefix, line[1:]))
    if current:
        hunks.append(current)
    return hunks


def _find_hunk_location(file_lines: list[str], expected: list[str]) -> int | None:
    if not expected:
        return len(file_lines)
    max_start = len(file_lines) - len(expected)
    for start in range(max_start + 1):
        matched = True
        for index, expected_line in enumerate(expected):
            if file_lines[start + index] != expected_line:
                matched = False
                break
        if matched:
            return start
    return None


def _strip_read_file_numbered_prefixes(lines: list[str]) -> tuple[list[str], bool]:
    pattern = re.compile(r"^\d+:\s")
    stripped_any = False
    stripped_lines: list[str] = []
    for line in lines:
        stripped = pattern.sub("", line, count=1)
        if stripped != line:
            stripped_any = True
        stripped_lines.append(stripped)
    return stripped_lines, stripped_any


def _apply_single_hunk(file_lines: list[str], hunk: list[tuple[str, str]]) -> list[str]:
    expected = [text for prefix, text in hunk if prefix in {" ", "-"}]
    location = _find_hunk_location(file_lines, expected)
    if location is None:
        stripped_expected, stripped_any = _strip_read_file_numbered_prefixes(expected)
        if stripped_any and _find_hunk_location(file_lines, stripped_expected) is not None:
            raise MCPToolError(
                -32602,
                "Failed to apply hunk: expected context was not found. Patch hunk appears to include read_file line numbers (e.g. '31: '). Remove numeric prefixes or call read_file with render=raw.",
            )
        raise MCPToolError(-32602, "Failed to apply hunk: expected context was not found.")
    output_block: list[str] = []
    input_index = location
    for prefix, text in hunk:
        if prefix == " ":
            if input_index >= len(file_lines) or file_lines[input_index] != text:
                raise MCPToolError(-32602, "Failed to apply hunk: context mismatch.")
            output_block.append(text)
            input_index += 1
            continue
        if prefix == "-":
            if input_index >= len(file_lines) or file_lines[input_index] != text:
                raise MCPToolError(-32602, "Failed to apply hunk: deletion mismatch.")
            input_index += 1
            continue
        output_block.append(text)
    return file_lines[:location] + output_block + file_lines[location + len(expected) :]


def _apply_update_patch(original_text: str, patch_lines: list[str]) -> str:
    trailing_newline = original_text.endswith("\n")
    file_lines = original_text.splitlines()
    hunks = _parse_update_hunks(patch_lines)
    for hunk in hunks:
        file_lines = _apply_single_hunk(file_lines, hunk)
    updated_text = "\n".join(file_lines)
    if trailing_newline:
        updated_text += "\n"
    return updated_text


def _resolve_patch_path(
    path_value: str,
    *,
    workspace_path: str,
    description: str,
) -> str:
    return resolve_path_under_workspace_or_tool_error(
        path_value,
        workspace_path=workspace_path,
        description=description,
    )


def _read_text_file(path: str, rel_path: str) -> str:
    try:
        with open_text(path, mode="r", encoding="utf-8", errors="replace") as file_handle:
            return file_handle.read()
    except OSError as os_exception:
        raise MCPToolError(
            -32602,
            f"Failed to read file {rel_path}: {os_exception}",
        ) from os_exception


def _get_current_content(path: str, rel_path: str, state: dict[str, str | None]) -> str | None:
    if path in state:
        return state[path]
    if not os.path.exists(path):
        state[path] = None
        return None
    if not os.path.isfile(path):
        raise MCPToolError(-32602, f"File is not a file: {rel_path}")
    content = _read_text_file(path, rel_path)
    state[path] = content
    return content


def parse_patch_operations(
    patch_lines: list[str],
    *,
    workspace_path: str,
) -> list[AddOperation | DeleteOperation | UpdateOperation]:
    operations: list[AddOperation | DeleteOperation | UpdateOperation] = []
    path_state: dict[str, str | None] = {}
    index = 1
    while index < len(patch_lines):
        line = patch_lines[index]
        if line.strip() == "*** End Patch":
            return operations
        if line.startswith("*** Add File: "):
            rel_path = line[len("*** Add File: ") :].strip()
            if not rel_path:
                raise MCPToolError(-32602, "Add File requires a non-empty path")
            target_path = _resolve_patch_path(
                rel_path,
                workspace_path=workspace_path,
                description="file",
            )
            existing_content = _get_current_content(target_path, rel_path, path_state)
            if existing_content is not None:
                raise MCPToolError(-32602, f"File already exists: {rel_path}")
            index += 1
            content_lines: list[str] = []
            while index < len(patch_lines) and not patch_lines[index].startswith("*** "):
                raw = patch_lines[index]
                if raw.startswith("+"):
                    content_lines.append(raw[1:])
                else:
                    content_lines.append(raw)
                index += 1
            content_text = f"{'\n'.join(content_lines)}\n"
            operations.append(
                AddOperation(
                    rel_path=rel_path,
                    target_path=target_path,
                    content_text=content_text,
                ),
            )
            path_state[target_path] = content_text
            continue
        if line.startswith("*** Delete File: "):
            rel_path = line[len("*** Delete File: ") :].strip()
            if not rel_path:
                raise MCPToolError(-32602, "Delete File requires a non-empty path")
            target_path = _resolve_patch_path(
                rel_path,
                workspace_path=workspace_path,
                description="file",
            )
            existing_content = _get_current_content(target_path, rel_path, path_state)
            if existing_content is None:
                raise MCPToolError(-32602, f"File is not a file: {rel_path}")
            operations.append(
                DeleteOperation(
                    rel_path=rel_path,
                    target_path=target_path,
                    deleted_content=existing_content,
                ),
            )
            path_state[target_path] = None
            index += 1
            continue
        if line.startswith("*** Update File: "):
            rel_path = line[len("*** Update File: ") :].strip()
            if not rel_path:
                raise MCPToolError(-32602, "Update File requires a non-empty path")
            source_path = _resolve_patch_path(
                rel_path,
                workspace_path=workspace_path,
                description="file",
            )
            original_text = _get_current_content(source_path, rel_path, path_state)
            if original_text is None:
                raise MCPToolError(-32602, f"File is not a file: {rel_path}")
            index += 1
            move_to: str | None = None
            dest_path = source_path
            if index < len(patch_lines) and patch_lines[index].startswith("*** Move to: "):
                move_to_value = patch_lines[index][len("*** Move to: ") :].strip()
                if not move_to_value:
                    raise MCPToolError(-32602, "Move to requires a non-empty path")
                move_to = move_to_value
                dest_path = _resolve_patch_path(
                    move_to,
                    workspace_path=workspace_path,
                    description="file",
                )
                index += 1
                if dest_path != source_path:
                    destination_content = _get_current_content(dest_path, move_to, path_state)
                    if destination_content is not None:
                        raise MCPToolError(-32602, f"Move destination already exists: {move_to}")
            update_lines: list[str] = []
            while index < len(patch_lines):
                candidate_line = patch_lines[index]
                if candidate_line.startswith("*** "):
                    if candidate_line.strip() == "*** End of File":
                        update_lines.append(candidate_line)
                        index += 1
                        continue
                    break
                update_lines.append(candidate_line)
                index += 1
            updated_text = _apply_update_patch(original_text, update_lines)
            diff_path = move_to if move_to is not None else rel_path
            operations.append(
                UpdateOperation(
                    rel_path=rel_path,
                    source_path=source_path,
                    dest_path=dest_path,
                    diff_path=diff_path,
                    original_text=original_text,
                    updated_text=updated_text,
                ),
            )
            if dest_path == source_path:
                path_state[source_path] = updated_text
            else:
                path_state[source_path] = None
                path_state[dest_path] = updated_text
            continue
        raise MCPToolError(-32602, f"Unknown patch directive: {line}")
    raise MCPToolError(-32602, "Input must end with '*** End Patch'")

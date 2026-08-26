"""SoAI - Canonical workspace filesystem MCP tool name list [backend/core/mcp/filesystem_tool_names.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ()

FILESYSTEM_MCP_TOOL_NAMES: tuple[str, ...] = (
    "apply_patch",
    "glob_files",
    "grep_files",
    "list_dir",
    "message_parse",
    "read_audio",
    "read_document",
    "read_file",
    "read_image",
    "read_video",
    "replace_in_file",
    "write_file",
)

"""SoAI - MCP registered tool workspace dependency policy [backend/mcp/registry/tool_workspace_requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.mcp.filesystem_tool_names import FILESYSTEM_MCP_TOOL_NAMES

__all__ = ("registered_tool_uses_runtime_workspace",)

_BROWSER_TOOL_PREFIX = "browser_"
_SHELL_TOOL_NAME = "shell"
_WORKSPACE_DEPENDENT_TOOL_NAMES: frozenset[str] = frozenset(
    (*FILESYSTEM_MCP_TOOL_NAMES, _SHELL_TOOL_NAME),
)


def registered_tool_uses_runtime_workspace(tool_name: str) -> bool:
    normalized_tool_name = tool_name.strip()
    return (
        normalized_tool_name.startswith(
            _BROWSER_TOOL_PREFIX,
        )
        or normalized_tool_name in _WORKSPACE_DEPENDENT_TOOL_NAMES
    )

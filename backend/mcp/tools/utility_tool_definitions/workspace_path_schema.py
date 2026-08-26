"""SoAI - MCP workspace file path schema builder [backend/mcp/tools/utility_tool_definitions/workspace_path_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_workspace_file_path_schema",)


def build_workspace_file_path_schema(*, description: str) -> JSONDict:
    return {
        "type": "string",
        "description": description,
    }

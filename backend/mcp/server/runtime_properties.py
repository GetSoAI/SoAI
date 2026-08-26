"""SoAI - MCP server property and listing helpers [backend/mcp/server/runtime_properties.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.server.internal_protocols import MCPServerRuntimePropertiesSurface

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "list_registered_prompt_names",
    "plugin_tool_definitions",
)


def list_registered_prompt_names(self: MCPServerRuntimePropertiesSurface) -> list[str]:
    return sorted(self.state.registration.registered_prompts)


def plugin_tool_definitions(_self: MCPServerRuntimePropertiesSurface) -> dict[str, JSONDict]:
    return {}

"""SoAI - MCP utility tool definition: vault_list [backend/mcp/tools/utility_tool_definitions/vault_list.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_LOCK
from mcp.tools.utility_tool_definitions.vault_schemas import (
    build_vault_credentials_output_schema,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_vault_list_tool_definitions",)


def build_vault_list_tool_definitions() -> dict[str, JSONDict]:
    return {
        "vault_list": {
            "title": "Vault List",
            "description": "List encrypted vault credentials (metadata only).",
            "icons": [build_tool_icon_entry(ICON_LOCK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
                "required": [],
            },
            "output_schema": build_vault_credentials_output_schema(),
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }

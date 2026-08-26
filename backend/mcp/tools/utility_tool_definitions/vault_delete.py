"""SoAI - MCP utility tool definition: vault_delete [backend/mcp/tools/utility_tool_definitions/vault_delete.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_LOCK

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_vault_delete_tool_definitions",)


def build_vault_delete_tool_definitions() -> dict[str, JSONDict]:
    return {
        "vault_delete": {
            "title": "Vault Delete",
            "description": "Delete a credential from the encrypted vault by id. Requires approval.",
            "icons": [build_tool_icon_entry(ICON_LOCK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "credential_id": {"type": "string", "description": "Vault credential id."},
                },
                "required": ["credential_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"deleted": {"type": "boolean"}},
                "required": ["deleted"],
            },
            "annotations": build_tool_annotation_flags(
                read_only=False,
                destructive=True,
                idempotent=False,
                open_world=False,
                requires_approval=True,
            ),
        },
    }

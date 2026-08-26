"""SoAI - MCP utility tool definition: vault_secret_request [backend/mcp/tools/utility_tool_definitions/vault_secret_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_LOCK

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_vault_secret_request_tool_definitions",)


def build_vault_secret_request_tool_definitions() -> dict[str, JSONDict]:
    return {
        "vault_secret_request": {
            "title": "Secret Prompt",
            "description": (
                "Request credentials from the WebUI without returning secrets to the model. "
                "The tool may optionally offer save-to-vault and returns only an opaque "
                "secret_handle plus optional saved credential metadata."
            ),
            "icons": [build_tool_icon_entry(ICON_LOCK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "current_page_url": {
                        "type": "string",
                        "description": "The current page URL used to derive and display the site scope.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional short title shown in the vault secret prompt UI.",
                    },
                    "message": {
                        "type": "string",
                        "description": "Optional helper text shown in the vault secret prompt UI.",
                    },
                    "allow_save_to_vault": {
                        "type": "boolean",
                        "description": "Whether the WebUI may offer saving the credential to the vault (default true).",
                    },
                },
                "required": ["current_page_url"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "secret_handle": {"type": "string"},
                    "saved_credential_id": {"type": ["string", "null"]},
                },
                "required": ["secret_handle", "saved_credential_id"],
            },
            "annotations": build_tool_annotation_flags(),
        },
    }

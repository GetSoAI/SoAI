"""SoAI - MCP utility tool definition: vault_login_request [backend/mcp/tools/utility_tool_definitions/vault_login_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_LOCK
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_vault_login_request_tool_definitions",)


def build_vault_login_request_tool_definitions() -> dict[str, JSONDict]:
    return {
        "vault_login_request": {
            "title": "Vault Prompt Login",
            "description": (
                "Request credentials via the WebUI and optionally save them to the encrypted vault. "
                "This tool requires approval and never returns secrets; it returns an opaque "
                "secret_handle plus save metadata only."
            ),
            "icons": [build_tool_icon_entry(ICON_LOCK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The active browser page URL; it must match the current page origin.",
                    },
                    "label_suggestion": {
                        "type": "string",
                        "description": "Optional label suggestion prefilled in the WebUI save-to-vault field.",
                    },
                    **build_browser_session_param_properties(),
                },
                "required": ["url"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "secret_handle": {"type": "string"},
                    "scope": {"type": "object"},
                    "saved": {"type": "boolean"},
                    "credential_id": {"type": ["string", "null"]},
                },
                "required": ["secret_handle", "scope", "saved", "credential_id"],
            },
            "annotations": build_tool_annotation_flags(
                read_only=False,
                destructive=False,
                idempotent=False,
                open_world=False,
                requires_approval=True,
            ),
        },
    }

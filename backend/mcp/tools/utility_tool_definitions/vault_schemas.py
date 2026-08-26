"""SoAI - MCP vault tool schemas [backend/mcp/tools/utility_tool_definitions/vault_schemas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_vault_credentials_output_schema",)


def build_vault_credentials_output_schema() -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "credentials": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "credential_id": {"type": "string"},
                        "label": {"type": "string"},
                        "scope": {"type": "object"},
                        "username_hint": {"type": ["string", "null"]},
                        "last_used_at_ms": {"type": ["integer", "null"]},
                    },
                    "required": [
                        "credential_id",
                        "label",
                        "scope",
                        "username_hint",
                        "last_used_at_ms",
                    ],
                },
            },
        },
        "required": ["credentials"],
    }

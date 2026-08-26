"""SoAI - MCP utility tool definitions: browser autofill [backend/mcp/tools/utility_tool_definitions/browser_autofill.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_SECRET, ICON_BROWSER_VAULT
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    non_empty_string_schema,
    nullable_boolean_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_autofill_tool_definitions",)


def build_browser_autofill_tool_definitions() -> dict[str, JSONDict]:
    base_refs: JSONDict = {
        "username_ref": nullable_non_empty_string_schema(
            description="Optional snapshot ref for the username/email field. If you provide refs explicitly, only the provided fields are filled (no heuristics for missing fields).",
        ),
        "password_ref": nullable_non_empty_string_schema(
            description="Optional snapshot ref for the password field. If omitted and username_ref is provided, the tool can fill only the username.",
        ),
        "submit": nullable_boolean_schema(
            description="Whether to submit the form after filling (press Enter on the filled password field when available, otherwise the filled username field). Required when the page is an HTTP Basic Auth prompt (no form fields).",
        ),
    }
    return {
        "browser_autofill_secret": {
            "title": "Browser Autofill (Secret Handle)",
            "description": (
                "Securely autofill login fields using a secret_handle from vault_secret_request or "
                "vault_login_request. Requires approval and uses the current page URL for scope "
                "validation. Secrets never appear in tool arguments or results."
            ),
            "icons": [build_tool_icon_entry(ICON_BROWSER_SECRET)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": non_empty_string_schema(
                        description="Claimed current page URL used for approval scoping.",
                    ),
                    "secret_handle": non_empty_string_schema(
                        description="Opaque secret handle returned by vault_secret_request or vault_login_request.",
                    ),
                    **base_refs,
                    **build_browser_session_param_properties(),
                },
                "required": ["url", "secret_handle"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"filled": {"type": "boolean"}, "submitted": {"type": "boolean"}},
                "required": ["filled", "submitted"],
            },
            "annotations": {
                **build_tool_annotation_flags(open_world=True),
                "requiresApprovalHint": True,
            },
        },
        "browser_autofill_vault": {
            "title": "Browser Autofill (Saved Vault Credential)",
            "description": (
                "Securely autofill login fields using a saved encrypted vault credential. "
                "Requires approval and uses the current page URL for scope validation. "
                "Secrets never appear in tool arguments or results. Use vault_login_request and choose to save to the vault to obtain a credential_id."
            ),
            "icons": [build_tool_icon_entry(ICON_BROWSER_VAULT)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "url": non_empty_string_schema(
                        description="Claimed current page URL used for approval scoping.",
                    ),
                    "credential_id": non_empty_string_schema(
                        description="Vault credential id (returned as credential_id by vault_login_request when saved).",
                    ),
                    **base_refs,
                    **build_browser_session_param_properties(),
                },
                "required": ["url", "credential_id"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"filled": {"type": "boolean"}, "submitted": {"type": "boolean"}},
                "required": ["filled", "submitted"],
            },
            "annotations": {
                **build_tool_annotation_flags(open_world=True),
                "requiresApprovalHint": True,
            },
        },
    }

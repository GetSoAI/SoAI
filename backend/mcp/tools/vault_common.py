"""SoAI - MCP vault credential validation and formatting [backend/mcp/tools/vault_common.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.argument_validation import require_non_empty_string_value
from core.validation.strings import coerce_optional_trimmed_str
from mcp.tools.argument_fields import require_non_empty_string
from mcp.tools.error import MCPToolError, get_arg

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "format_vault_credential",
    "require_vault_credential_id",
)


def require_vault_credential_id(arguments: JSONDict) -> str:
    return require_non_empty_string(
        get_arg(arguments, "credential_id"),
        key="credential_id",
        type_message="credential_id must be a non-empty string.",
        empty_message="credential_id must be a non-empty string.",
    )


def format_vault_credential(item: JSONDict) -> JSONDict:
    credential_id = require_non_empty_string_value(
        item.get("credential_id"),
        build_error=lambda message: MCPToolError(-32603, message),
        type_message="vault credential row is invalid.",
        empty_message="vault credential row is invalid.",
    )
    label = require_non_empty_string_value(
        item.get("label"),
        build_error=lambda message: MCPToolError(-32603, message),
        type_message="vault credential row is invalid.",
        empty_message="vault credential row is invalid.",
    )
    scope_value = item.get("scope")
    if not isinstance(scope_value, dict):
        raise MCPToolError(-32603, "vault credential row is invalid.")
    username_hint = coerce_optional_trimmed_str(item.get("username_hint"))
    last_used_raw = item.get("last_used_at_ms")
    last_used_at_ms = (
        int(last_used_raw) if isinstance(last_used_raw, int) and last_used_raw > 0 else None
    )
    return {
        "credential_id": credential_id,
        "label": label,
        "scope": scope_value,
        "username_hint": username_hint,
        "last_used_at_ms": last_used_at_ms,
    }

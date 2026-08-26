"""SoAI - Browser snapshot capture config parsing [backend/mcp/tools/browser/snapshot_capture_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "parse_snapshot_roles",
    "resolve_snapshot_max_chars",
    "resolve_snapshot_max_refs",
)


def resolve_snapshot_max_chars(utility_tools: MCPUtilityToolsProtocol) -> int:
    raw = utility_tools.config.get_int("TOOLS.MCP.BROWSER.SNAPSHOT_MAX_CHARS")
    if not is_strict_int(raw):
        return 20000
    return max(1000, int(raw))


def resolve_snapshot_max_refs(utility_tools: MCPUtilityToolsProtocol) -> int:
    return 500 if resolve_snapshot_max_chars(utility_tools) >= 20000 else 200


def parse_snapshot_roles(value: JSONValue, *, field_name: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise MCPToolError(-32602, f"{field_name} must be a non-empty string array")
    roles: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise MCPToolError(-32602, f"{field_name} must be a non-empty string array")
        normalized = item.strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        roles.append(normalized)
    return tuple(roles)

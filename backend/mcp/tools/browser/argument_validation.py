"""SoAI - Browser tool argument validation helpers [backend/mcp/tools/browser/argument_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import require_non_empty_string
from mcp.tools.argument_scalars import parse_bool_strict_default
from mcp.tools.browser.snapshot_capture import parse_snapshot_roles
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict, JSONValue

    type PageWaitUntil = Literal["commit", "load", "domcontentloaded", "networkidle"]

__all__ = (
    "parse_inline_snapshot_request",
    "parse_optional_wait_until_strict",
)


def parse_optional_wait_until_strict(value: JSONValue, *, field_name: str) -> PageWaitUntil | None:
    if value is None:
        return None
    normalized = require_non_empty_string(
        value,
        key=field_name,
        type_message=f"{field_name} must be one of: commit, load, domcontentloaded, networkidle",
        empty_message=f"{field_name} must be one of: commit, load, domcontentloaded, networkidle",
    ).lower()
    if normalized == "commit":
        return "commit"
    if normalized == "load":
        return "load"
    if normalized == "domcontentloaded":
        return "domcontentloaded"
    if normalized == "networkidle":
        return "networkidle"
    raise MCPToolError(
        -32602,
        f"{field_name} must be one of: commit, load, domcontentloaded, networkidle",
    )


def parse_inline_snapshot_request(arguments: JSONDict) -> tuple[bool, tuple[str, ...] | None]:
    include_snapshot = parse_bool_strict_default(
        arguments.get("include_snapshot"),
        field_name="include_snapshot",
        default=False,
    )
    snapshot_roles = parse_snapshot_roles(
        arguments.get("snapshot_roles"),
        field_name="snapshot_roles",
    )
    if not include_snapshot and snapshot_roles is not None:
        raise MCPToolError(-32602, "snapshot_roles is only allowed when include_snapshot=true")
    return include_snapshot, snapshot_roles

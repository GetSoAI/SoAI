"""SoAI - Browser navigation argument parsing [backend/mcp/tools/browser/navigation_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_scalars import parse_optional_int_strict
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONDict

    type NavigateWaitUntil = Literal["load", "domcontentloaded", "networkidle"]

__all__ = (
    "resolve_navigate_wait_until",
    "resolve_navigation_tab_id",
    "resolve_navigation_timeout_ms",
)


def resolve_navigate_wait_until(arguments: JSONDict) -> NavigateWaitUntil:
    raw = arguments.get("wait_until")
    if raw is None:
        return "domcontentloaded"
    if not isinstance(raw, str) or not raw.strip():
        raise MCPToolError(
            -32602,
            "wait_until must be one of: load, domcontentloaded, networkidle (networkidle0/networkidle2 are unsupported)",
        )
    value = raw.strip().lower()
    if value == "load":
        return "load"
    if value == "domcontentloaded":
        return "domcontentloaded"
    if value == "networkidle":
        return "networkidle"
    raise MCPToolError(
        -32602,
        "wait_until must be one of: load, domcontentloaded, networkidle (networkidle0/networkidle2 are unsupported)",
    )


def resolve_navigation_timeout_ms(arguments: JSONDict) -> int | None:
    return parse_optional_int_strict(
        arguments.get("timeout_ms"),
        field_name="timeout_ms",
        min_value=1,
        max_value=300_000,
    )


def resolve_navigation_tab_id(arguments: JSONDict) -> int | None:
    tab_id_value = parse_optional_int_strict(
        arguments.get("tab_id"),
        field_name="tab_id",
        min_value=0,
        max_value=1000,
    )
    if tab_id_value is None:
        return None
    return int(tab_id_value)

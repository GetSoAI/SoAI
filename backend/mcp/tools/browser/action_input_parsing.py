"""SoAI - Browser action input parsing [backend/mcp/tools/browser/action_input_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from typing import Literal

    from core.types.json import JSONValue

    type MouseButton = Literal["left", "right", "middle"]
    type ModifierKey = Literal["Alt", "Control", "ControlOrMeta", "Meta", "Shift"]

__all__ = (
    "parse_button",
    "parse_modifiers",
)


def parse_button(value: JSONValue) -> MouseButton:
    if value is None:
        return "left"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "left":
            return "left"
        if normalized == "right":
            return "right"
        if normalized == "middle":
            return "middle"
    raise MCPToolError(-32602, "button must be one of: left, right, middle")


def _parse_modifier(value: str) -> ModifierKey | None:
    normalized = value.strip()
    if normalized == "Alt":
        return "Alt"
    if normalized == "Control":
        return "Control"
    if normalized == "ControlOrMeta":
        return "ControlOrMeta"
    if normalized == "Meta":
        return "Meta"
    if normalized == "Shift":
        return "Shift"
    return None


def parse_modifiers(value: JSONValue) -> list[ModifierKey]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise MCPToolError(
            -32602,
            "modifiers must be an array containing only: Alt, Control, ControlOrMeta, Meta, Shift",
        )
    output: list[ModifierKey] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise MCPToolError(
                -32602,
                "modifiers must be an array containing only: Alt, Control, ControlOrMeta, Meta, Shift",
            )
        parsed = _parse_modifier(item)
        if parsed is not None:
            output.append(parsed)
            continue
        raise MCPToolError(
            -32602,
            "modifiers must be an array containing only: Alt, Control, ControlOrMeta, Meta, Shift",
        )
    return output

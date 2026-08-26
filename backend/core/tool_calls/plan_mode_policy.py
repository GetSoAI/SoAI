"""SoAI - Plan-mode tool policy [backend/core/tool_calls/plan_mode_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("plan_mode_block_reason",)


def _extract_annotations(tool_entry: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    raw_entry = coerce_json_dict(tool_entry.get("raw"))
    if raw_entry is None:
        return {}
    annotations = coerce_json_dict(raw_entry.get("annotations"))
    if annotations is None:
        return {}
    return annotations


def plan_mode_block_reason(tool_name: str, tool_entry: Mapping[str, JSONValue]) -> str | None:
    annotations = _extract_annotations(tool_entry)
    destructive_hint = annotations.get("destructiveHint")
    if not isinstance(destructive_hint, bool):
        return f"Tool '{tool_name}' is not allowed in plan mode because it does not declare destructive metadata."
    if destructive_hint:
        return f"Tool '{tool_name}' is not allowed in plan mode because it is marked destructive."
    return None

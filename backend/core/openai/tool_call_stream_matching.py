"""SoAI - Tool-call stream matching helpers [backend/core/openai/tool_call_stream_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Hashable
from typing import TYPE_CHECKING

from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "THINKING_CLOSE_TAG_REGEX",
    "THINKING_OPEN_TAG_REGEX",
    "has_known_tool_call",
    "resolve_tool_call_key",
    "source_has_content",
    "source_has_reasoning",
)

THINKING_OPEN_TAG_REGEX = r"^<\s*(thinking|think)(\s[^>]*)?>$"
THINKING_CLOSE_TAG_REGEX = r"^<\s*/\s*(thinking|think)\s*>$"


def resolve_tool_call_key(call: JSONDict) -> Hashable | None:
    call_id = call.get("id")
    if isinstance(call_id, str) and call_id:
        return call_id
    call_index = coerce_optional_non_negative_int_strict(call.get("index"))
    if call_index is not None:
        return call_index
    return None


def has_known_tool_call(tool_calls: dict[Hashable, JSONDict], call: JSONDict) -> bool:
    call_id = call.get("id")
    if isinstance(call_id, str) and call_id and call_id in tool_calls:
        return True
    call_index = coerce_optional_non_negative_int_strict(call.get("index"))
    if call_index is not None and call_index in tool_calls:
        return True
    return False


def source_has_content(source: JSONDict | None) -> bool:
    return isinstance(source, dict) and "content" in source


def source_has_reasoning(source: JSONDict | None) -> bool:
    return isinstance(source, dict) and (
        "reasoning_content" in source or "reasoning" in source or "thinking" in source
    )

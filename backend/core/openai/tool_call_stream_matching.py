"""SoAI - Tool-call stream matching helpers [backend/core/openai/tool_call_stream_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections.abc import Hashable
from typing import TYPE_CHECKING

from core.openai.reasoning_text import REASONING_FIELD_NAMES
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "THINKING_CLOSE_TAG_REGEX",
    "THINKING_OPEN_TAG_REGEX",
    "find_text_tag_start",
    "is_thinking_tag_prefix",
    "has_known_tool_call",
    "resolve_tool_call_key",
    "source_has_content",
    "source_has_reasoning",
)

_THINKING_TAG_NAMES = ("thinking", "think")
THINKING_OPEN_TAG_REGEX = r"^<\s*(thinking|think)(\s[^>]*)?>$"
THINKING_CLOSE_TAG_REGEX = r"^<\s*/\s*(thinking|think)\s*>$"
_TEXT_TAG_NAME_REGEX = r"<\s*(/?\s*)([A-Za-z]*)"


def find_text_tag_start(text: str, start: int) -> int:
    tag_name_pattern = re.compile(_TEXT_TAG_NAME_REGEX)
    tag_index = text.find("<", start)
    while tag_index != -1:
        prefix = tag_name_pattern.match(text, tag_index)
        if prefix is not None:
            if prefix.group(2) or prefix.end() == len(text):
                return tag_index
            if text[prefix.end()] in {"!", "?"}:
                return tag_index
        tag_index = text.find("<", tag_index + 1)
    return -1


def is_thinking_tag_prefix(text: str) -> bool:
    prefix = re.match(_TEXT_TAG_NAME_REGEX, text)
    if prefix is None:
        return False
    name = prefix.group(2).lower()
    suffix_index = prefix.end()
    if suffix_index == len(text):
        return any(tag_name.startswith(name) for tag_name in _THINKING_TAG_NAMES)
    if name not in _THINKING_TAG_NAMES or not text[suffix_index].isspace():
        return False
    closing = prefix.group(1).startswith("/")
    return not closing or not text[suffix_index:].strip()


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
    return isinstance(source, dict) and any(key in source for key in REASONING_FIELD_NAMES)

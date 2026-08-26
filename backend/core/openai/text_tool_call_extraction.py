"""SoAI - Textual OpenAI tool-call extraction [backend/core/openai/text_tool_call_extraction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.openai.content_text_rendering import render_openai_content_text
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, JSONValue

__all__ = (
    "TextToolCallExtraction",
    "contains_text_tool_call_markup",
    "extract_text_tool_calls",
)

_TOOL_CALL_BLOCK_PATTERN_TEXT = r"<tool_call>\s*(.*?)\s*</tool_call>"


@dataclass(frozen=True, slots=True)
class TextToolCallExtraction:
    tool_calls: list[JSONDict]
    sanitized_text: str


def contains_text_tool_call_markup(text: str) -> bool:
    return bool(text and re.search(r"</?tool_call\s*>", text, re.IGNORECASE))


def _iter_candidate_payloads(text: str) -> list[tuple[str, JSONValue]]:
    candidates: list[tuple[str, JSONValue]] = []
    for match in re.finditer(_TOOL_CALL_BLOCK_PATTERN_TEXT, text, re.DOTALL):
        parsed = _parse_candidate(match.group(1))
        if parsed is not None:
            candidates.append((match.group(0), parsed))
    return candidates


def _parse_candidate(raw: str) -> JSONValue | None:
    normalized = str(raw or "").strip()
    if not normalized:
        return None
    try:
        return parse_json_value(normalized, field="text_tool_call")
    except ValidationError:
        return None


def _iter_tool_call_objects(value: JSONValue) -> list[JSONDict]:
    if isinstance(value, dict):
        tool_calls = value.get("tool_calls")
        if isinstance(tool_calls, list):
            return [dict(entry) for entry in tool_calls if isinstance(entry, dict)]
        return [dict(value)]
    if isinstance(value, list):
        return [dict(entry) for entry in value if isinstance(entry, dict)]
    return []


def _coerce_arguments(value: JSONValue) -> JSONValue | None:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _coerce_text_tool_call(
    *,
    value: JSONDict,
    offered_tool_names: frozenset[str],
) -> JSONDict | None:
    name_value = value.get("name")
    if not isinstance(name_value, str) or name_value.strip() not in offered_tool_names:
        return None
    arguments = _coerce_arguments(value.get("arguments"))
    if arguments is None:
        return None
    return {
        "type": "function",
        "function": {
            "name": name_value.strip(),
            "arguments": (
                arguments
                if isinstance(arguments, str)
                else serialize_json_compact_stable(arguments)
            ),
        },
    }


def extract_text_tool_calls(
    *,
    assistant_content: JSONValue,
    offered_tool_names: frozenset[str],
) -> TextToolCallExtraction:
    assistant_text = render_openai_content_text(assistant_content)
    sanitized_text = assistant_text
    tool_calls: list[JSONDict] = []
    if not assistant_text.strip() or not offered_tool_names:
        return TextToolCallExtraction(tool_calls=[], sanitized_text=assistant_text)
    for raw_block, payload in _iter_candidate_payloads(assistant_text):
        block_calls: list[JSONDict] = []
        for entry in _iter_tool_call_objects(payload):
            tool_call = _coerce_text_tool_call(
                value=entry,
                offered_tool_names=offered_tool_names,
            )
            if tool_call is not None:
                block_calls.append(tool_call)
        if not block_calls:
            continue
        tool_calls.extend(block_calls)
        sanitized_text = sanitized_text.replace(raw_block, "").strip()
    return TextToolCallExtraction(tool_calls=tool_calls, sanitized_text=sanitized_text)

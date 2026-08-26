"""SoAI - Tool result prompt shaping primitives [backend/core/tool_calls/tool_result_prompt_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MAX_EMERGENCY_PASSES",
    "REDACTION_KEY",
    "TRUNCATED_KEY",
    "ToolResultPromptShapingStats",
    "depth_truncation_payload",
    "omit_items_payload",
    "redaction_payload",
    "safe_json_dumps",
)

REDACTION_KEY: str = "__soai_redacted__"
TRUNCATED_KEY: str = "__soai_truncated__"
MAX_EMERGENCY_PASSES: int = 8


@dataclass(slots=True)
class ToolResultPromptShapingStats:
    tool_name: str
    original_chars: int
    shaped_chars: int
    redacted_binary_base64: int = 0
    truncated_strings: int = 0
    omitted_keys: int = 0
    omitted_items: int = 0
    max_depth_truncations: int = 0
    emergency_drops: int = 0

    @property
    def changed(self) -> bool:
        return bool(
            self.redacted_binary_base64
            or self.truncated_strings
            or self.omitted_keys
            or self.omitted_items
            or self.max_depth_truncations
            or self.emergency_drops
            or (self.shaped_chars != self.original_chars),
        )


def safe_json_dumps(value: JSONValue) -> str:
    try:
        normalized = normalize_for_json(value)
    except ValidationError:
        normalized = {"value": str(value)}
    return serialize_json_compact_stable_strict(normalized, ensure_ascii=False)


def redaction_payload(*, reason: str, original_chars: int) -> JSONDict:
    return {
        REDACTION_KEY: {
            "reason": str(reason),
            "original_chars": int(original_chars),
        },
    }


def depth_truncation_payload() -> JSONDict:
    return {TRUNCATED_KEY: {"reason": "max_depth"}}


def omit_items_payload(*, omitted_items: int) -> JSONDict:
    return {TRUNCATED_KEY: {"omitted_items": int(omitted_items)}}

"""SoAI - Reasoning payload normalization helpers [backend/core/openai/reasoning_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("normalize_reasoning_text",)


def normalize_reasoning_text(payload: JSONValue | None, visited: set[int] | None = None) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, bool):
        return "true" if payload else "false"
    if isinstance(payload, int | float):
        return str(payload)
    if isinstance(payload, list):
        visited_set = visited or set()
        payload_identity = id(payload)
        if payload_identity in visited_set:
            return ""
        visited_set.add(payload_identity)
        return "".join(normalize_reasoning_text(item, visited_set) for item in payload)
    if isinstance(payload, dict):
        visited_set = visited or set()
        payload_identity = id(payload)
        if payload_identity in visited_set:
            return ""
        visited_set.add(payload_identity)
        text_value = payload.get("text")
        if isinstance(text_value, str):
            return text_value
        delta_value = payload.get("delta")
        if isinstance(delta_value, str):
            return delta_value
        summary_text_value = payload.get("summary_text")
        if isinstance(summary_text_value, str):
            return summary_text_value
        output_text_value = payload.get("output_text")
        if isinstance(output_text_value, str):
            return output_text_value
        if "reasoning_content" in payload:
            return normalize_reasoning_text(payload.get("reasoning_content"), visited_set)
        if "reasoning" in payload:
            return normalize_reasoning_text(payload.get("reasoning"), visited_set)
        if "summary" in payload:
            return normalize_reasoning_text(payload.get("summary"), visited_set)
        if "thinking" in payload:
            return normalize_reasoning_text(payload.get("thinking"), visited_set)
        has_message_wrapper_shape = "message" in payload or "role" in payload
        if has_message_wrapper_shape:
            return ""
        if "content" in payload:
            return normalize_reasoning_text(payload.get("content"), visited_set)
        if "parts" in payload:
            return normalize_reasoning_text(payload.get("parts"), visited_set)
        if "value" in payload:
            return normalize_reasoning_text(payload.get("value"), visited_set)
    return ""

"""SoAI - OpenAI content field to plain text coercion [backend/core/openai/content_text_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("coerce_openai_content_text",)


def coerce_openai_content_text(value: JSONValue) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            item_text = coerce_openai_content_text(item)
            if item_text:
                parts.append(item_text)
        return "".join(parts)
    if isinstance(value, dict):
        text_value = value.get("text")
        if isinstance(text_value, str) and text_value:
            return text_value
        nested_value = value.get("value")
        if isinstance(nested_value, str) and nested_value:
            return nested_value
        if "content" in value:
            return coerce_openai_content_text(value.get("content"))
        if "parts" in value:
            return coerce_openai_content_text(value.get("parts"))
    return ""

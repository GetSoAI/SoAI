"""SoAI - OpenAI content field readable text rendering [backend/core/openai/content_text_rendering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.serialization.json import try_serialize_json_compact_stable_default_str
from core.types.json import JSONValue

__all__ = ("render_openai_content_text",)


def _normalize_image_url_for_text(url_value: str) -> str:
    url = url_value.strip()
    if not url:
        return ""
    if not url.startswith("data:"):
        return url if len(url) <= 512 else f"{url[:512]}..."
    marker = ";base64,"
    marker_index = url.find(marker)
    if marker_index >= 0:
        return url[: marker_index + len(marker)]
    return url[:256]


def render_openai_content_text(value: JSONValue) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for entry in value:
            if isinstance(entry, dict):
                entry_type = entry.get("type")
                if entry_type == "text":
                    text_value = entry.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        parts.append(text_value.strip())
                    continue
                if entry_type == "image_url":
                    image_url_value = entry.get("image_url")
                    url_value = (
                        image_url_value.get("url") if isinstance(image_url_value, dict) else None
                    )
                    if isinstance(url_value, str) and url_value.strip():
                        parts.append(f"[image_url] {_normalize_image_url_for_text(url_value)}")
                    else:
                        parts.append("[image_url]")
                    continue
                if entry_type == "input_audio":
                    input_audio_value = entry.get("input_audio")
                    format_value = (
                        input_audio_value.get("format")
                        if isinstance(input_audio_value, dict)
                        else None
                    )
                    if isinstance(format_value, str) and format_value.strip():
                        parts.append(f"[input_audio] format={format_value.strip()}")
                    else:
                        parts.append("[input_audio]")
                    continue
                serialized = try_serialize_json_compact_stable_default_str(
                    entry,
                    ensure_ascii=False,
                )
                if isinstance(serialized, str) and serialized.strip():
                    parts.append(serialized.strip())
                continue
            serialized = try_serialize_json_compact_stable_default_str(entry, ensure_ascii=False)
            if isinstance(serialized, str) and serialized.strip():
                parts.append(serialized.strip())
                continue
            parts.append(str(entry))
        return "\n".join(part for part in parts if part).strip()
    serialized_dict = try_serialize_json_compact_stable_default_str(value, ensure_ascii=False)
    if isinstance(serialized_dict, str) and serialized_dict.strip():
        return serialized_dict
    return str(value)

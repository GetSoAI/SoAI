"""SoAI - OpenAI Responses input modality inference [backend/core/openai/responses_input_modalities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("infer_required_modalities_from_responses_input",)


def infer_required_modalities_from_responses_input(input_value: JSONValue) -> tuple[str, ...]:
    if not isinstance(input_value, list):
        return ()
    required: list[str] = []
    for item in input_value:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for segment in content:
            if not isinstance(segment, dict):
                continue
            segment_type = str(segment.get("type", "")).strip().lower()
            if segment_type in ("image_url", "input_image", "image"):
                if "vision" not in required:
                    required.append("vision")
            elif segment_type in ("input_audio", "audio"):
                if "audio" not in required:
                    required.append("audio")
    return tuple(required)

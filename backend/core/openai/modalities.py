"""SoAI - OpenAI capability taxonomy and modality detection [backend/core/openai/modalities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from core.openai.capability_taxonomy import (
    OPENAI_FEATURE_MATRIX,
    OpenAIChatFeature,
    OpenAIEndpoint,
    OpenAIImageFeature,
    OpenAIModality,
)
from core.types.json import JSONValue

__all__ = (
    "collect_message_modalities",
    "get_openai_capability_taxonomy",
)


def iter_enum_values(enum_cls: type[Enum]) -> tuple[str, ...]:
    return tuple(member.value for member in enum_cls)


def get_openai_capability_taxonomy() -> dict[str, tuple[str, ...]]:
    responses_features: tuple[str, ...] = ()
    for category, entries in OPENAI_FEATURE_MATRIX:
        if category == "responses_features":
            responses_features = tuple(token for token, _flag in entries)
            break
    return {
        "endpoints": iter_enum_values(OpenAIEndpoint),
        "image_features": iter_enum_values(OpenAIImageFeature),
        "chat_features": iter_enum_values(OpenAIChatFeature),
        "responses_features": responses_features,
        "modalities": iter_enum_values(OpenAIModality),
    }


def collect_message_modalities(messages: JSONValue) -> tuple[str, ...]:
    if not isinstance(messages, list):
        return ()
    detected: list[str] = []
    for message in messages:
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for segment in content:
            if not isinstance(segment, dict):
                continue
            segment_type = str(segment.get("type", "")).strip().lower()
            if not segment_type:
                continue
            if segment_type in ("image_url", "input_image", "image"):
                if OpenAIModality.VISION.value not in detected:
                    detected.append(OpenAIModality.VISION.value)
            elif segment_type in ("input_audio", "audio"):
                if OpenAIModality.AUDIO.value not in detected:
                    detected.append(OpenAIModality.AUDIO.value)
    return tuple(detected)

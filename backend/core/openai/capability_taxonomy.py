"""SoAI - OpenAI capability taxonomy (core) [backend/core/openai/capability_taxonomy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

__all__ = (
    "OPENAI_CAPABILITY_CATEGORIES",
    "OPENAI_FEATURE_MATRIX",
    "OpenAIChatFeature",
    "OpenAIEndpoint",
    "OpenAIImageFeature",
    "OpenAIModality",
)


class OpenAIModality(str, Enum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"


class OpenAIEndpoint(str, Enum):
    CHAT_COMPLETIONS = "chat_completions"
    COMPLETIONS = "completions"
    RESPONSES = "responses"
    EMBEDDINGS = "embeddings"
    IMAGES = "images"
    AUDIO_TRANSCRIPTIONS = "audio_transcriptions"
    AUDIO_TRANSLATIONS = "audio_translations"
    AUDIO_SPEECH = "audio_speech"


class OpenAIImageFeature(str, Enum):
    IMAGE_EDITS = "image_edits"
    IMAGE_VARIATIONS = "image_variations"


class OpenAIChatFeature(str, Enum):
    VISION = "vision"
    INPUT_AUDIO = "input_audio"
    TOOL_CALLING = "tool_calling"
    PARALLEL_TOOL_CALLS = "parallel_tool_calls"
    STRUCTURED_OUTPUT = "structured_output"
    JSON_SCHEMA = "json_schema"


_OPENAI_CATEGORY_ENDPOINTS = "endpoints"
_OPENAI_CATEGORY_IMAGE_FEATURES = "image_features"
_OPENAI_CATEGORY_CHAT_FEATURES = "chat_features"
_OPENAI_CATEGORY_RESPONSES_FEATURES = "responses_features"

OPENAI_CAPABILITY_CATEGORIES: tuple[str, ...] = (
    _OPENAI_CATEGORY_ENDPOINTS,
    _OPENAI_CATEGORY_IMAGE_FEATURES,
    _OPENAI_CATEGORY_CHAT_FEATURES,
    _OPENAI_CATEGORY_RESPONSES_FEATURES,
)


OPENAI_FEATURE_MATRIX: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        _OPENAI_CATEGORY_ENDPOINTS,
        (
            (OpenAIEndpoint.CHAT_COMPLETIONS.value, "SUPPORTS_CHAT_COMPLETIONS"),
            (OpenAIEndpoint.COMPLETIONS.value, "SUPPORTS_COMPLETIONS"),
            (OpenAIEndpoint.RESPONSES.value, "SUPPORTS_RESPONSES"),
            (OpenAIEndpoint.EMBEDDINGS.value, "SUPPORTS_EMBEDDINGS"),
            (OpenAIEndpoint.IMAGES.value, "SUPPORTS_IMAGES"),
            (OpenAIEndpoint.AUDIO_TRANSCRIPTIONS.value, "SUPPORTS_AUDIO_TRANSCRIPTIONS"),
            (OpenAIEndpoint.AUDIO_TRANSLATIONS.value, "SUPPORTS_AUDIO_TRANSLATIONS"),
            (OpenAIEndpoint.AUDIO_SPEECH.value, "SUPPORTS_AUDIO_SPEECH"),
        ),
    ),
    (
        _OPENAI_CATEGORY_IMAGE_FEATURES,
        (
            (OpenAIImageFeature.IMAGE_EDITS.value, "SUPPORTS_IMAGE_EDITS"),
            (OpenAIImageFeature.IMAGE_VARIATIONS.value, "SUPPORTS_IMAGE_VARIATIONS"),
        ),
    ),
    (
        _OPENAI_CATEGORY_CHAT_FEATURES,
        (
            (OpenAIChatFeature.VISION.value, "SUPPORTS_VISION"),
            (OpenAIChatFeature.INPUT_AUDIO.value, "SUPPORTS_INPUT_AUDIO"),
            (OpenAIChatFeature.TOOL_CALLING.value, "SUPPORTS_TOOL_CALLING"),
            (OpenAIChatFeature.PARALLEL_TOOL_CALLS.value, "SUPPORTS_PARALLEL_TOOL_CALLS"),
            (OpenAIChatFeature.STRUCTURED_OUTPUT.value, "SUPPORTS_STRUCTURED_OUTPUT"),
            (OpenAIChatFeature.JSON_SCHEMA.value, "SUPPORTS_JSON_SCHEMA"),
        ),
    ),
    (
        _OPENAI_CATEGORY_RESPONSES_FEATURES,
        (
            ("create", "SUPPORTS_RESPONSES"),
            ("retrieve", "SUPPORTS_RESPONSES_RETRIEVE"),
            ("delete", "SUPPORTS_RESPONSES_DELETE"),
            ("cancel", "SUPPORTS_RESPONSES_CANCEL"),
            ("input_items", "SUPPORTS_RESPONSES_INPUT_ITEMS"),
            ("input_tokens", "SUPPORTS_RESPONSES_INPUT_TOKENS"),
        ),
    ),
)

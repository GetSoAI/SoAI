"""SoAI - Current OpenAI compatibility contract snapshots [backend/core/openai/openai_current.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.openai_current_media import (
    AUDIO_SPEECH_CREATE_FIELDS,
    AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS,
    AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS,
    FILES_CREATE_MULTIPART_FIELDS,
    IMAGES_EDITS_CREATE_MULTIPART_FIELDS,
    IMAGES_GENERATIONS_CREATE_FIELDS,
    IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS,
)

__all__ = (
    "AUDIO_SPEECH_CREATE_FIELDS",
    "AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS",
    "AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS",
    "CHAT_COMPLETIONS_CREATE_FIELDS",
    "CHAT_COMPLETIONS_MODIFY_FIELDS",
    "COMPLETIONS_CREATE_FIELDS",
    "EMBEDDINGS_CREATE_FIELDS",
    "FILES_CREATE_MULTIPART_FIELDS",
    "IMAGES_EDITS_CREATE_MULTIPART_FIELDS",
    "IMAGES_GENERATIONS_CREATE_FIELDS",
    "IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS",
    "OPENAI_ENDPOINT_FIELD_SNAPSHOTS",
    "RESPONSES_COMPACT_FIELDS",
    "RESPONSES_CREATE_FIELDS",
    "RESPONSES_INPUT_TOKENS_FIELDS",
)

CHAT_COMPLETIONS_CREATE_FIELDS = frozenset(
    {
        "audio",
        "frequency_penalty",
        "function_call",
        "functions",
        "logit_bias",
        "logprobs",
        "max_completion_tokens",
        "max_tokens",
        "messages",
        "metadata",
        "modalities",
        "model",
        "n",
        "parallel_tool_calls",
        "prediction",
        "presence_penalty",
        "prompt_cache_key",
        "prompt_cache_options",
        "prompt_cache_retention",
        "reasoning_effort",
        "response_format",
        "safety_identifier",
        "seed",
        "service_tier",
        "stop",
        "store",
        "stream",
        "stream_options",
        "temperature",
        "tool_choice",
        "tools",
        "top_logprobs",
        "top_p",
        "user",
        "verbosity",
        "web_search_options",
    },
)

CHAT_COMPLETIONS_MODIFY_FIELDS = frozenset({"metadata"})

COMPLETIONS_CREATE_FIELDS = frozenset(
    {
        "best_of",
        "echo",
        "frequency_penalty",
        "logit_bias",
        "logprobs",
        "max_tokens",
        "model",
        "n",
        "presence_penalty",
        "prompt",
        "seed",
        "stop",
        "stream",
        "stream_options",
        "suffix",
        "temperature",
        "top_p",
        "user",
    },
)

RESPONSES_CREATE_FIELDS = frozenset(
    {
        "background",
        "client_metadata",
        "context_management",
        "conversation",
        "include",
        "input",
        "instructions",
        "max_output_tokens",
        "max_tool_calls",
        "metadata",
        "model",
        "parallel_tool_calls",
        "previous_response_id",
        "prompt",
        "prompt_cache_key",
        "prompt_cache_options",
        "prompt_cache_retention",
        "reasoning",
        "safety_identifier",
        "service_tier",
        "store",
        "stream",
        "stream_options",
        "temperature",
        "text",
        "tool_choice",
        "tools",
        "top_logprobs",
        "top_p",
        "truncation",
        "user",
    },
)

RESPONSES_INPUT_TOKENS_FIELDS = frozenset(
    {
        "conversation",
        "input",
        "instructions",
        "model",
        "parallel_tool_calls",
        "previous_response_id",
        "reasoning",
        "text",
        "tool_choice",
        "tools",
        "truncation",
    },
)

RESPONSES_COMPACT_FIELDS = frozenset(
    {
        "input",
        "instructions",
        "model",
        "previous_response_id",
        "prompt_cache_key",
    },
)

EMBEDDINGS_CREATE_FIELDS = frozenset(
    {
        "dimensions",
        "encoding_format",
        "input",
        "model",
        "user",
    },
)

OPENAI_ENDPOINT_FIELD_SNAPSHOTS: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    ("/chat/completions", "post", "application/json", CHAT_COMPLETIONS_CREATE_FIELDS),
    (
        "/chat/completions/{completion_id}",
        "post",
        "application/json",
        CHAT_COMPLETIONS_MODIFY_FIELDS,
    ),
    ("/completions", "post", "application/json", COMPLETIONS_CREATE_FIELDS),
    ("/responses", "post", "application/json", RESPONSES_CREATE_FIELDS),
    (
        "/responses/input_tokens",
        "post",
        "application/json",
        RESPONSES_INPUT_TOKENS_FIELDS,
    ),
    ("/responses/compact", "post", "application/json", RESPONSES_COMPACT_FIELDS),
    ("/embeddings", "post", "application/json", EMBEDDINGS_CREATE_FIELDS),
    (
        "/images/generations",
        "post",
        "application/json",
        IMAGES_GENERATIONS_CREATE_FIELDS,
    ),
    (
        "/images/edits",
        "post",
        "multipart/form-data",
        IMAGES_EDITS_CREATE_MULTIPART_FIELDS,
    ),
    (
        "/images/variations",
        "post",
        "multipart/form-data",
        IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS,
    ),
    (
        "/audio/transcriptions",
        "post",
        "multipart/form-data",
        AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS,
    ),
    (
        "/audio/translations",
        "post",
        "multipart/form-data",
        AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS,
    ),
    ("/audio/speech", "post", "application/json", AUDIO_SPEECH_CREATE_FIELDS),
    ("/files", "post", "multipart/form-data", FILES_CREATE_MULTIPART_FIELDS),
)

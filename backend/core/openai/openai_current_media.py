"""SoAI - Current OpenAI media endpoint contract snapshots [backend/core/openai/openai_current_media.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "AUDIO_SPEECH_CREATE_FIELDS",
    "AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS",
    "AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS",
    "FILES_CREATE_MULTIPART_FIELDS",
    "IMAGES_EDITS_CREATE_MULTIPART_FIELDS",
    "IMAGES_GENERATIONS_CREATE_FIELDS",
    "IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS",
)

IMAGES_GENERATIONS_CREATE_FIELDS = frozenset(
    {
        "background",
        "model",
        "moderation",
        "n",
        "output_compression",
        "output_format",
        "partial_images",
        "prompt",
        "quality",
        "response_format",
        "size",
        "stream",
        "style",
        "user",
    },
)

IMAGES_EDITS_CREATE_MULTIPART_FIELDS = frozenset(
    {
        "background",
        "image",
        "input_fidelity",
        "mask",
        "model",
        "n",
        "output_compression",
        "output_format",
        "partial_images",
        "prompt",
        "quality",
        "response_format",
        "size",
        "stream",
        "user",
    },
)

IMAGES_VARIATIONS_CREATE_MULTIPART_FIELDS = frozenset(
    {
        "image",
        "model",
        "n",
        "response_format",
        "size",
        "user",
    },
)

AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS = frozenset(
    {
        "chunking_strategy",
        "file",
        "include",
        "known_speaker_names",
        "known_speaker_references",
        "language",
        "model",
        "prompt",
        "response_format",
        "stream",
        "temperature",
        "timestamp_granularities",
    },
)

AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS = frozenset(
    {
        "file",
        "model",
        "prompt",
        "response_format",
        "temperature",
    },
)

AUDIO_SPEECH_CREATE_FIELDS = frozenset(
    {
        "input",
        "instructions",
        "model",
        "response_format",
        "speed",
        "stream_format",
        "voice",
    },
)

FILES_CREATE_MULTIPART_FIELDS = frozenset(
    {
        "expires_after",
        "file",
        "purpose",
    },
)

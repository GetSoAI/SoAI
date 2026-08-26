"""SoAI - OpenAI audio upload field sets [backend/core/openai/audio_upload_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.openai_current_media import (
    AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS,
    AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS,
)

__all__ = (
    "OPENAI_AUDIO_TRANSCRIPTION_ALLOWED_FIELDS",
    "OPENAI_AUDIO_TRANSLATION_ALLOWED_FIELDS",
)

OPENAI_AUDIO_TRANSCRIPTION_ALLOWED_FIELDS: frozenset[str] = frozenset(
    (
        *AUDIO_TRANSCRIPTIONS_CREATE_MULTIPART_FIELDS,
        "include[]",
        "known_speaker_names[]",
        "known_speaker_references[]",
        "timestamp_granularities[]",
    ),
)

OPENAI_AUDIO_TRANSLATION_ALLOWED_FIELDS: frozenset[str] = frozenset(
    (*AUDIO_TRANSLATIONS_CREATE_MULTIPART_FIELDS,),
)

"""SoAI - OpenAI audio request schemas [backend/features/api/schemas/openai_audio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from core.errors.exceptions import ValidationError
from core.meta.soai_v1 import SoAIV1StrictModel
from core.types.json import JSONValue
from features.api.schemas.openai_numeric_validation import reject_boolean_numeric_value

__all__ = (
    "CustomVoiceReference",
    "TextToSpeechRequestFields",
    "TextToSpeechRequest",
    "WebuiTextToSpeechRequest",
    "normalize_audio_voice_reference",
)

TTS_INPUT_MAX_CHARS: int = 4_096


class CustomVoiceReference(SoAIV1StrictModel):
    id: str = Field(..., min_length=1, max_length=256)


def normalize_audio_voice_reference(value: JSONValue) -> JSONValue:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValidationError("voice must not be boolean.")
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise ValidationError("voice must be a non-empty string.")
        return normalized
    if isinstance(value, dict):
        voice_id = value.get("id")
        if not isinstance(voice_id, str) or not voice_id.strip():
            raise ValidationError("voice.id must be a non-empty string.")
        return voice_id.strip()
    raise ValidationError("voice must be a string or an object.")


class TextToSpeechRequestFields(SoAIV1StrictModel):
    model: str = Field(..., min_length=1, description="TTS model ID.")
    input: str = Field(
        ...,
        min_length=1,
        max_length=TTS_INPUT_MAX_CHARS,
        description="The text to generate audio for.",
    )
    instructions: str | None = Field(
        None,
        max_length=TTS_INPUT_MAX_CHARS,
        description="Additional instructions for the voice.",
    )
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = Field(
        "mp3",
        description="The audio output format.",
    )
    speed: float = Field(1.0, ge=0.25, le=4.0, description="The speed of the generated audio.")

    @field_validator("speed", mode="before")
    @classmethod
    def reject_boolean_speed(cls, value: JSONValue) -> JSONValue:
        return reject_boolean_numeric_value(value, message="speed must be numeric, not boolean.")

    @field_validator("voice", mode="before", check_fields=False)
    @classmethod
    def normalize_voice(cls, value: JSONValue) -> JSONValue:
        return normalize_audio_voice_reference(value)


class TextToSpeechRequest(TextToSpeechRequestFields):
    voice: str | CustomVoiceReference = Field(
        ...,
        description="Built-in voice name or custom voice reference.",
    )
    stream_format: Literal["sse", "audio"] = Field(
        "audio",
        description="Streaming response format.",
    )


class WebuiTextToSpeechRequest(TextToSpeechRequestFields):
    voice: str | CustomVoiceReference | None = Field(
        None,
        description="Built-in voice name or custom voice reference.",
    )

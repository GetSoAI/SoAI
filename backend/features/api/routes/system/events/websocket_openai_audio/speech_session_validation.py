"""SoAI - WebSocket OpenAI speech session validation [backend/features/api/routes/system/events/websocket_openai_audio/speech_session_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict
from core.validation.strict_numbers import require_non_negative_int_strict
from features.api.runtime.openai_tts_request_preparation import (
    prepare_text_to_speech_request,
)
from features.api.schemas.openai_audio import (
    TTS_INPUT_MAX_CHARS,
    WebuiTextToSpeechRequest,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "build_speech_session_payload",
    "require_speech_session_input",
    "require_speech_session_segment_sequence",
)


async def build_speech_session_payload(
    *,
    data: JSONDict,
    api_context: ApiContext,
) -> tuple[JSONDict, str]:
    payload_value = coerce_json_dict(data.get("payload"))
    if payload_value is None:
        raise ValidationError("payload is required.")
    probe_payload = dict(payload_value)
    probe_payload["input"] = "SoAI voice call speech session probe."
    tts_payload = WebuiTextToSpeechRequest.model_validate(probe_payload)
    if tts_payload.response_format != "wav":
        raise ValidationError("Voice call speech sessions require response_format='wav'.")
    prepared = await prepare_text_to_speech_request(
        api_context=api_context,
        request=tts_payload,
        include_input=False,
    )
    return prepared.payload, prepared.media_type


def require_speech_session_segment_sequence(data: JSONDict) -> int:
    return require_non_negative_int_strict(
        data.get("segment_sequence"),
        error_message="segment_sequence must be a non-negative integer.",
    )


def require_speech_session_input(data: JSONDict) -> str:
    value = data.get("input")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("input must be a non-empty string.")
    if len(value) > TTS_INPUT_MAX_CHARS:
        raise ValidationError(f"input must contain at most {TTS_INPUT_MAX_CHARS} characters.")
    return value.strip()

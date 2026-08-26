"""SoAI - OpenAI text-to-speech request preparation [backend/features/api/runtime/openai_tts_request_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.openai.tts_media_types import resolve_tts_response_media_type
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from features.api.runtime.context import ApiContext
from features.api.runtime.openai_audio_model_resolution import (
    is_auto_audio_model_selector,
    resolve_audio_model_id,
)
from features.api.schemas.openai_audio import (
    TextToSpeechRequest,
    WebuiTextToSpeechRequest,
)

__all__ = (
    "TTS_MODELS_UNAVAILABLE_MESSAGE",
    "PreparedTextToSpeechRequest",
    "prepare_text_to_speech_request",
)

TTS_MODELS_UNAVAILABLE_MESSAGE = (
    "No TTS models available. Install/enable a plugin that supports OpenAI audio speech."
)


@dataclass(frozen=True, slots=True)
class PreparedTextToSpeechRequest[
    TextToSpeechRequestType: (TextToSpeechRequest, WebuiTextToSpeechRequest)
]:
    request: TextToSpeechRequestType
    payload: JSONDict
    media_type: str
    resolved_model_id: str | None


async def prepare_text_to_speech_request[TextToSpeechRequestType: (
    TextToSpeechRequest,
    WebuiTextToSpeechRequest,
)](
    *,
    api_context: ApiContext,
    request: TextToSpeechRequestType,
    include_input: bool,
) -> PreparedTextToSpeechRequest[TextToSpeechRequestType]:
    resolved_model_id = None
    prepared_request = request
    if is_auto_audio_model_selector(request.model):
        resolved_model_id = await resolve_audio_model_id(
            api_context,
            request.model,
            endpoint_capability="audio_speech",
            unavailable_message=TTS_MODELS_UNAVAILABLE_MESSAGE,
            preferred_model_reference=(request.voice if isinstance(request.voice, str) else None),
        )
        prepared_request = request.model_copy(update={"model": resolved_model_id})
    media_type = resolve_tts_response_media_type(prepared_request.response_format)
    payload = coerce_json_dict(prepared_request.model_dump(exclude_none=True, exclude_unset=True))
    if payload is None:
        raise ValidationError("Text-to-speech payload could not be serialized.")
    if not include_input:
        payload.pop("input", None)
    payload["_request_type"] = "audio_speech"
    return PreparedTextToSpeechRequest(
        request=prepared_request,
        payload=payload,
        media_type=media_type,
        resolved_model_id=resolved_model_id,
    )

"""SoAI - OpenAI audio model auto-resolution [backend/features/api/runtime/openai_audio_model_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError, ValidationError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import apply_public_error_payload
from core.media.speech_errors import TRANSCRIPTION_MODEL_UNAVAILABLE_CODE
from core.openai.audio_model_selection import (
    is_auto_audio_model_selector,
    model_supports_openai_audio_endpoint,
)
from features.api.runtime.context import ApiContext

__all__ = (
    "TEXT_TO_SPEECH_MODEL_UNAVAILABLE_CODE",
    "resolve_audio_model_id",
    "resolve_audio_upload_model_fields",
)

TEXT_TO_SPEECH_MODEL_UNAVAILABLE_CODE = "text_to_speech_model_unavailable"


def _model_matches_reference(model_id: str, reference: str | None) -> bool:
    if reference is None:
        return False
    normalized_reference = reference.strip()
    if not normalized_reference or "/" not in normalized_reference:
        return False
    return model_id == normalized_reference or model_id.endswith(f"/{normalized_reference}")


async def resolve_audio_model_id(
    api_context: ApiContext,
    requested_model: str,
    *,
    endpoint_capability: str,
    unavailable_message: str,
    preferred_model_reference: str | None = None,
) -> str:
    normalized_requested = requested_model.strip()
    if not is_auto_audio_model_selector(normalized_requested):
        return normalized_requested
    available_models = (
        await api_context.dependencies.model_information_service.model_get_available()
    )
    if not isinstance(available_models, list):
        raise StateError("Model information service returned an invalid available-models result.")
    capable_model_ids: list[str] = []
    for model in available_models:
        if not model_supports_openai_audio_endpoint(model, endpoint_capability):
            continue
        model_id_value = model.get("id")
        model_id = model_id_value.strip() if isinstance(model_id_value, str) else ""
        if not model_id:
            continue
        capable_model_ids.append(model_id)
    candidates = sorted(dict.fromkeys(capable_model_ids))
    if not candidates:
        error = ValidationError(unavailable_message)
        if endpoint_capability == "audio_transcriptions":
            apply_public_error_payload(
                error,
                ErrorPublicPayload(
                    code=TRANSCRIPTION_MODEL_UNAVAILABLE_CODE,
                    message=unavailable_message,
                    http_status=400,
                    details={"speech_scope": "voice"},
                ),
            )
        elif endpoint_capability == "audio_speech":
            apply_public_error_payload(
                error,
                ErrorPublicPayload(
                    code=TEXT_TO_SPEECH_MODEL_UNAVAILABLE_CODE,
                    message=unavailable_message,
                    http_status=400,
                ),
            )
        raise error
    for candidate in candidates:
        if _model_matches_reference(candidate, preferred_model_reference):
            return candidate
    return candidates[0]


async def resolve_audio_upload_model_fields(
    *,
    api_context: ApiContext,
    fields: dict[str, tuple[str, ...]],
    endpoint_capability: str,
    unavailable_message: str,
) -> dict[str, tuple[str, ...]]:
    resolved_fields = dict(fields)
    model_values = resolved_fields.get("model")
    model = model_values[0].strip() if isinstance(model_values, tuple) and model_values else ""
    if not model or not is_auto_audio_model_selector(model):
        return resolved_fields
    resolved_model_id = await resolve_audio_model_id(
        api_context,
        model,
        endpoint_capability=endpoint_capability,
        unavailable_message=unavailable_message,
    )
    resolved_fields["model"] = (resolved_model_id,)
    return resolved_fields

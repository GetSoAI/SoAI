"""SoAI - OpenAI request requirement mismatch helpers [backend/core/openai/request_requirement_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.openai.capability_taxonomy import (
    OpenAIChatFeature,
    OpenAIEndpoint,
    OpenAIImageFeature,
    OpenAIModality,
)
from core.types.json import JSONDict, JSONValue

__all__ = (
    "OpenAIRequestRequirementMismatch",
    "build_openai_request_requirement_failure_details",
    "build_openai_request_requirement_failure_message",
    "classify_openai_request_requirement_mismatch",
)


@dataclass(frozen=True, slots=True)
class OpenAIRequestRequirementMismatch:
    missing_capabilities: tuple[str, ...]
    missing_modalities: tuple[str, ...]


def build_openai_request_requirement_failure_message(
    mismatch: OpenAIRequestRequirementMismatch,
) -> str:
    normalized = _normalize_mismatch(mismatch)
    message_parts = ["Unsupported request requirements."]
    if normalized.missing_modalities:
        message_parts.append(f"Missing modalities: {', '.join(normalized.missing_modalities)}.")
    if normalized.missing_capabilities:
        message_parts.append(f"Missing capabilities: {', '.join(normalized.missing_capabilities)}.")
    message_parts.append("Fix: select a compatible model or adjust the request.")
    return " ".join(message_parts)


def build_openai_request_requirement_failure_details(
    mismatch: OpenAIRequestRequirementMismatch,
) -> JSONDict:
    normalized = _normalize_mismatch(mismatch)
    return {
        "missing_capabilities": list(normalized.missing_capabilities),
        "missing_modalities": list(normalized.missing_modalities),
    }


def classify_openai_request_requirement_mismatch(
    *,
    message: str | None,
    details: JSONDict | None = None,
) -> OpenAIRequestRequirementMismatch | None:
    if isinstance(details, dict):
        mismatch = _classify_from_details(details)
        if mismatch is not None:
            return mismatch
    if not isinstance(message, str):
        return None
    normalized_message = message.strip().lower()
    if not normalized_message:
        return None
    if not _looks_like_requirement_mismatch(normalized_message):
        return None
    missing_capabilities = _collect_detected_tokens(
        normalized_message,
        (
            OpenAIChatFeature.VISION.value,
            OpenAIChatFeature.INPUT_AUDIO.value,
            OpenAIChatFeature.TOOL_CALLING.value,
            OpenAIChatFeature.PARALLEL_TOOL_CALLS.value,
            OpenAIChatFeature.STRUCTURED_OUTPUT.value,
            OpenAIChatFeature.JSON_SCHEMA.value,
            OpenAIEndpoint.RESPONSES.value,
            OpenAIEndpoint.CHAT_COMPLETIONS.value,
            OpenAIEndpoint.COMPLETIONS.value,
            OpenAIEndpoint.IMAGES.value,
            OpenAIEndpoint.AUDIO_SPEECH.value,
            OpenAIEndpoint.AUDIO_TRANSCRIPTIONS.value,
            OpenAIEndpoint.AUDIO_TRANSLATIONS.value,
            OpenAIImageFeature.IMAGE_EDITS.value,
            OpenAIImageFeature.IMAGE_VARIATIONS.value,
        ),
    )
    missing_modalities = _collect_detected_tokens(
        normalized_message,
        (
            OpenAIModality.VISION.value,
            OpenAIModality.AUDIO.value,
        ),
    )
    if (
        _contains_image_input_rejection(normalized_message)
        and OpenAIModality.VISION.value not in missing_modalities
    ):
        missing_modalities = (*missing_modalities, OpenAIModality.VISION.value)
    if (
        "vision-capable" in normalized_message
        and OpenAIModality.VISION.value not in missing_modalities
    ):
        missing_modalities = (*missing_modalities, OpenAIModality.VISION.value)
    if (
        "multimodal processing is not enabled" in normalized_message
        and OpenAIModality.VISION.value not in missing_modalities
    ):
        missing_modalities = (*missing_modalities, OpenAIModality.VISION.value)
    if not missing_capabilities and not missing_modalities:
        return None
    return _normalize_mismatch(
        OpenAIRequestRequirementMismatch(
            missing_capabilities=missing_capabilities,
            missing_modalities=missing_modalities,
        ),
    )


def _classify_from_details(
    details: JSONDict,
) -> OpenAIRequestRequirementMismatch | None:
    missing_capabilities = _coerce_string_tuple(details.get("missing_capabilities"))
    missing_modalities = _coerce_string_tuple(details.get("missing_modalities"))
    if not missing_capabilities and not missing_modalities:
        return None
    return _normalize_mismatch(
        OpenAIRequestRequirementMismatch(
            missing_capabilities=missing_capabilities,
            missing_modalities=missing_modalities,
        ),
    )


def _normalize_mismatch(
    mismatch: OpenAIRequestRequirementMismatch,
) -> OpenAIRequestRequirementMismatch:
    filtered_capabilities = tuple(
        capability
        for capability in mismatch.missing_capabilities
        if capability not in mismatch.missing_modalities
    )
    return OpenAIRequestRequirementMismatch(
        missing_capabilities=filtered_capabilities,
        missing_modalities=mismatch.missing_modalities,
    )


def _coerce_string_tuple(value: JSONValue | None) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        token = item.strip().lower()
        if token and token not in normalized:
            normalized.append(token)
    return tuple(normalized)


def _looks_like_requirement_mismatch(message: str) -> bool:
    return (
        "unsupported request requirements" in message
        or "missing modalities:" in message
        or "missing capabilities:" in message
        or "does not support" in message
        or "unsupported modalit" in message
        or "unsupported capabilit" in message
        or "request contains modalit" in message
        or _contains_image_input_rejection(message)
        or "received multimodal data" in message
        or "multimodal processing is not enabled" in message
        or "enable-multimodal" in message
        or "select a compatible model" in message
    )


def _contains_image_input_rejection(message: str) -> bool:
    return "image content" in message or "image input" in message


def _collect_detected_tokens(
    message: str,
    candidates: tuple[str, ...],
) -> tuple[str, ...]:
    detected: list[str] = []
    for candidate in candidates:
        if _message_mentions_token(message, candidate) and candidate not in detected:
            detected.append(candidate)
    return tuple(detected)


def _message_mentions_token(message: str, token: str) -> bool:
    normalized_token = token.replace("_", " ")
    return normalized_token in message or token in message

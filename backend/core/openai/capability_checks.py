"""SoAI - OpenAI capability predicate helpers [backend/core/openai/capability_checks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.validation.boolean_coercion import coerce_bool_with_default

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "has_openai_modality",
    "has_openai_model_modality",
    "is_openai_audio_input_supported",
    "is_openai_capability_enabled",
    "is_openai_input_feature_supported",
    "is_openai_model_audio_input_supported",
    "is_openai_model_capability_enabled",
    "is_openai_model_vision_input_supported",
    "is_openai_vision_input_supported",
    "normalize_openai_capability_token",
)


def normalize_openai_capability_token(token: str) -> str:
    return str(token or "").strip().lower()


def is_openai_capability_enabled(
    openai_capabilities: Mapping[str, JSONValue],
    category: str,
    token: str,
) -> bool:
    normalized_token = normalize_openai_capability_token(token)
    if not normalized_token:
        return False
    flat_value = openai_capabilities.get(normalized_token)
    if flat_value is not None:
        return coerce_bool_with_default(flat_value, default=False, strict=False)
    nested_value = openai_capabilities.get(category)
    if isinstance(nested_value, Mapping):
        return coerce_bool_with_default(
            nested_value.get(normalized_token),
            default=False,
            strict=False,
        )
    return False


def has_openai_modality(modalities: JSONValue, token: str) -> bool:
    normalized_token = normalize_openai_capability_token(token)
    if not normalized_token or not isinstance(modalities, list):
        return False
    for entry in modalities:
        if not isinstance(entry, str):
            continue
        if normalize_openai_capability_token(entry) == normalized_token:
            return True
    return False


def is_openai_input_feature_supported(
    *,
    modalities: JSONValue,
    openai_capabilities: JSONValue,
    modality_token: str,
    capability_token: str,
) -> bool:
    if not has_openai_modality(modalities, modality_token):
        return False
    if not isinstance(openai_capabilities, Mapping):
        return True
    return is_openai_capability_enabled(
        openai_capabilities,
        "chat_features",
        capability_token,
    )


def is_openai_vision_input_supported(
    *,
    modalities: JSONValue,
    openai_capabilities: JSONValue,
) -> bool:
    return is_openai_input_feature_supported(
        modalities=modalities,
        openai_capabilities=openai_capabilities,
        modality_token="vision",
        capability_token="vision",
    )


def is_openai_audio_input_supported(
    *,
    modalities: JSONValue,
    openai_capabilities: JSONValue,
) -> bool:
    return is_openai_input_feature_supported(
        modalities=modalities,
        openai_capabilities=openai_capabilities,
        modality_token="audio",
        capability_token="input_audio",
    )


def is_openai_model_capability_enabled(
    model_entry: Mapping[str, JSONValue],
    *,
    category: str,
    token: str,
) -> bool:
    openai_capabilities = model_entry.get("openai_capabilities")
    if not isinstance(openai_capabilities, Mapping):
        return False
    return is_openai_capability_enabled(openai_capabilities, category, token)


def has_openai_model_modality(
    model_entry: Mapping[str, JSONValue],
    *,
    token: str,
) -> bool:
    return has_openai_modality(model_entry.get("modalities"), token)


def is_openai_model_vision_input_supported(model_entry: Mapping[str, JSONValue]) -> bool:
    return is_openai_vision_input_supported(
        modalities=model_entry.get("modalities"),
        openai_capabilities=model_entry.get("openai_capabilities"),
    )


def is_openai_model_audio_input_supported(model_entry: Mapping[str, JSONValue]) -> bool:
    return is_openai_audio_input_supported(
        modalities=model_entry.get("modalities"),
        openai_capabilities=model_entry.get("openai_capabilities"),
    )

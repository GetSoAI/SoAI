"""SoAI - Core effective OpenAI capability profile resolution [backend/core/openai/effective_profile.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.capabilities import normalize_openai_capabilities
from core.openai.capability_checks import is_openai_capability_enabled
from core.openai.capability_taxonomy import (
    OPENAI_CAPABILITY_CATEGORIES,
    OpenAIChatFeature,
    OpenAIEndpoint,
    OpenAIImageFeature,
    OpenAIModality,
)
from core.openai.compatibility import normalize_openai_modalities_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_openai_capability_overrides_payload",
    "compute_effective_openai_model_profile",
    "is_openai_capability_enabled",
    "normalize_openai_base_modalities",
    "parse_openai_capability_overrides",
)

_OPENAI_OVERRIDE_CATEGORIES: frozenset[str] = frozenset(
    ("endpoints", "image_features", "chat_features", "responses_features", "modalities"),
)
_VISION_CHAT_FEATURE_TOKEN = OpenAIChatFeature.VISION.value
_AUDIO_CHAT_FEATURE_TOKEN = OpenAIChatFeature.INPUT_AUDIO.value
_IMAGES_ENDPOINT_TOKEN = OpenAIEndpoint.IMAGES.value
_IMAGE_FEATURE_TOKENS: tuple[str, ...] = (
    OpenAIImageFeature.IMAGE_EDITS.value,
    OpenAIImageFeature.IMAGE_VARIATIONS.value,
)


def parse_openai_capability_overrides(value: JSONValue) -> dict[str, set[str]]:
    if isinstance(value, str):
        overrides = normalize_openai_capabilities(value)
    elif isinstance(value, Mapping):
        overrides = {
            str(cap_key): cap_value
            for cap_key, cap_value in value.items()
            if isinstance(cap_key, str)
        }
    else:
        overrides = {}
    disabled_value = overrides.get("disabled")
    if not isinstance(disabled_value, Mapping):
        return {}
    disabled: dict[str, set[str]] = {}
    for category, tokens_value in disabled_value.items():
        if not isinstance(category, str) or category not in _OPENAI_OVERRIDE_CATEGORIES:
            continue
        if not isinstance(tokens_value, Sequence) or isinstance(tokens_value, str | bytes):
            continue
        tokens = {
            str(token).strip().lower()
            for token in tokens_value
            if isinstance(token, str) and token.strip()
        }
        if tokens:
            disabled[category] = tokens
    return disabled


def build_openai_capability_overrides_payload(
    disabled: Mapping[str, set[str]],
) -> JSONDict | None:
    disabled_payload: JSONDict = {}
    for category in _OPENAI_OVERRIDE_CATEGORIES:
        tokens = disabled.get(category)
        if not tokens:
            continue
        normalized = sorted({token.strip().lower() for token in tokens if token.strip()})
        if normalized:
            disabled_payload[category] = normalized
    if not disabled_payload:
        return None
    return {"disabled": disabled_payload}


def compute_effective_openai_model_profile(
    *,
    base_modalities: JSONValue,
    base_openai_capabilities: JSONValue,
    overrides: JSONValue,
) -> tuple[list[str], JSONDict]:
    normalized_base_modalities = normalize_openai_base_modalities(
        base_modalities,
        invalid_collection_message="base_modalities must be a list of OpenAI modalities.",
        invalid_entry_message="base_modalities must contain only OpenAI modality strings.",
        empty_entry_message="base_modalities must not contain empty modality values.",
    )
    base_caps = (
        normalize_openai_capabilities(base_openai_capabilities)
        if not isinstance(base_openai_capabilities, Mapping)
        else normalize_openai_capabilities(dict(base_openai_capabilities))
    )
    disabled = parse_openai_capability_overrides(overrides)
    disabled_modalities = disabled.get("modalities") or set()
    effective_modalities = [
        modality for modality in normalized_base_modalities if modality not in disabled_modalities
    ]
    if not effective_modalities:
        raise ValidationError("OpenAI capability overrides must not disable all modalities.")
    effective_caps: JSONDict = dict(base_caps)
    for category in OPENAI_CAPABILITY_CATEGORIES:
        category_disabled = disabled.get(category) or set()
        if not category_disabled:
            continue
        for token in category_disabled:
            if token in effective_caps:
                effective_caps[token] = False
        section_value = effective_caps.get(category)
        if isinstance(section_value, Mapping):
            section: JSONDict = dict(section_value)
            changed = False
            for token in category_disabled:
                if token not in section:
                    continue
                if section[token] is not False:
                    section[token] = False
                    changed = True
            if changed:
                effective_caps[category] = section
    if "modalities" in effective_caps:
        modalities_value = effective_caps.get("modalities")
        if isinstance(modalities_value, list):
            effective_caps["modalities"] = list(effective_modalities)
    if OpenAIModality.VISION.value not in effective_modalities:
        _force_disable_capability(effective_caps, "chat_features", _VISION_CHAT_FEATURE_TOKEN)
    if OpenAIModality.AUDIO.value not in effective_modalities:
        _force_disable_capability(effective_caps, "chat_features", _AUDIO_CHAT_FEATURE_TOKEN)
    if not is_openai_capability_enabled(effective_caps, "endpoints", _IMAGES_ENDPOINT_TOKEN):
        for token in _IMAGE_FEATURE_TOKENS:
            _force_disable_capability(effective_caps, "image_features", token)
    return (list(effective_modalities), effective_caps)


def _force_disable_capability(openai_caps: JSONDict, category: str, token: str) -> None:
    normalized_token = str(token or "").strip().lower()
    if not normalized_token:
        return
    if normalized_token in openai_caps:
        openai_caps[normalized_token] = False
    section_value = openai_caps.get(category)
    if isinstance(section_value, Mapping):
        if normalized_token not in section_value:
            return
        section = dict(section_value)
        section[normalized_token] = False
        openai_caps[category] = section


def normalize_openai_base_modalities(
    value: JSONValue,
    *,
    invalid_collection_message: str,
    invalid_entry_message: str,
    empty_entry_message: str,
) -> list[str]:
    if (not isinstance(value, Sequence)) or isinstance(value, str | bytes):
        raise ValidationError(invalid_collection_message)
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(invalid_entry_message)
        text = item.strip().lower()
        if not text:
            raise ValidationError(empty_entry_message)
        normalized.append(text)
    return normalize_openai_modalities_strict(normalized, field_name="modalities")

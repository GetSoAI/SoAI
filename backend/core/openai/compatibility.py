"""SoAI - OpenAI compatibility enums and normalization helpers [backend/core/openai/compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from core.errors.exceptions import ValidationError
from core.openai.capability_taxonomy import OpenAIModality

__all__ = (
    "ExternalProviderMode",
    "normalize_external_provider_mode",
    "normalize_openai_modalities",
    "normalize_openai_modalities_strict",
    "normalize_openai_modality",
)


class ExternalProviderMode(str, Enum):
    NONE = "none"
    USER_MANAGED = "user_managed"
    PLUGIN_MANAGED = "plugin_managed"


def normalize_external_provider_mode(
    value: ExternalProviderMode | Enum | str | None,
) -> ExternalProviderMode:
    if isinstance(value, ExternalProviderMode):
        return value
    if isinstance(value, Enum):
        raw = value.value
        if isinstance(raw, str):
            candidate = raw.strip().lower()
        else:
            candidate = str(raw).strip().lower()
        if candidate:
            for mode in ExternalProviderMode:
                if candidate in {mode.value, mode.name.lower()}:
                    return mode
    if isinstance(value, str):
        candidate = value.strip().lower()
        for mode in ExternalProviderMode:
            if candidate in {mode.value, mode.name.lower()}:
                return mode
    return ExternalProviderMode.NONE


def normalize_openai_modality(value: OpenAIModality | str | None) -> str | None:
    if isinstance(value, OpenAIModality):
        return value.value
    if value is None:
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if candidate in (
        OpenAIModality.TEXT.value,
        OpenAIModality.VISION.value,
        OpenAIModality.AUDIO.value,
    ):
        return candidate
    return None


def normalize_openai_modalities(
    values: Iterable[OpenAIModality | str | None] | None,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        resolved = normalize_openai_modality(value)
        if resolved and resolved not in seen:
            seen.add(resolved)
            normalized.append(resolved)
    if not normalized:
        normalized = [OpenAIModality.TEXT.value]
    return normalized


def normalize_openai_modalities_strict(
    values: Iterable[OpenAIModality | str | None] | None,
    *,
    field_name: str = "modalities",
) -> list[str]:
    if values is None:
        raise ValidationError(f"Manifest field '{field_name}' must be a list of modalities.")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        resolved = normalize_openai_modality(value)
        if resolved is None:
            raise ValidationError(
                f"Manifest field '{field_name}' contains an unknown OpenAI modality '{value}'.",
            )
        if resolved not in seen:
            seen.add(resolved)
            normalized.append(resolved)
    if not normalized:
        raise ValidationError(f"Manifest field '{field_name}' must not be empty.")
    return normalized

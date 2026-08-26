"""SoAI - Scheduler plugin capability/modality requirements [backend/orchestrator/scheduling/plugin_requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.capability_checks import (
    has_openai_modality,
    is_openai_audio_input_supported,
    is_openai_capability_enabled,
    is_openai_vision_input_supported,
)
from core.openai.capability_taxonomy import OPENAI_CAPABILITY_CATEGORIES, OpenAIModality

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "RequirementEvaluation",
    "evaluate_model_requirements",
)


@dataclass(frozen=True, slots=True)
class RequirementEvaluation:
    meets: bool
    missing_capabilities: tuple[str, ...]
    missing_modalities: tuple[str, ...]


def evaluate_model_requirements(
    *,
    model_info: Mapping[str, JSONValue],
    capabilities: tuple[str, ...],
    modalities: tuple[str, ...],
) -> RequirementEvaluation:
    openai_caps_value = model_info.get("openai_capabilities")
    openai_caps: Mapping[str, JSONValue] = (
        openai_caps_value if isinstance(openai_caps_value, Mapping) else {}
    )
    missing_capabilities: list[str] = []
    for capability in capabilities or ():
        supported = any(
            is_openai_capability_enabled(openai_caps, category, capability)
            for category in OPENAI_CAPABILITY_CATEGORIES
        )
        if not supported:
            missing_capabilities.append(capability)
    missing_modalities: list[str] = []
    for modality in modalities or ():
        if modality == OpenAIModality.VISION.value:
            if not is_openai_vision_input_supported(
                modalities=model_info.get("modalities"),
                openai_capabilities=model_info.get("openai_capabilities"),
            ):
                missing_modalities.append(modality)
            continue
        if modality == OpenAIModality.AUDIO.value:
            if not is_openai_audio_input_supported(
                modalities=model_info.get("modalities"),
                openai_capabilities=model_info.get("openai_capabilities"),
            ):
                missing_modalities.append(modality)
            continue
        if not has_openai_modality(model_info.get("modalities"), modality):
            missing_modalities.append(modality)
    missing_capabilities_sorted = tuple(sorted(dict.fromkeys(missing_capabilities)))
    missing_modalities_sorted = tuple(sorted(dict.fromkeys(missing_modalities)))
    return RequirementEvaluation(
        meets=(not missing_capabilities_sorted) and (not missing_modalities_sorted),
        missing_capabilities=missing_capabilities_sorted,
        missing_modalities=missing_modalities_sorted,
    )

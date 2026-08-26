"""SoAI - OpenAI profile resolution helpers [backend/models/capabilities/openai_profile_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.capabilities import normalize_openai_capabilities
from core.openai.compatibility import normalize_openai_modalities_strict
from core.openai.effective_profile import compute_effective_openai_model_profile
from core.validation.boolean_coercion import coerce_bool_with_default

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "compose_model_openai_base_profile",
    "build_virtual_openai_profile",
    "resolve_effective_openai_profile",
)


def compose_model_openai_base_profile(
    *,
    plugin_profile: JSONDict,
    model_data: JSONDict,
) -> JSONDict:
    base_profile: JSONDict = {}
    model_modalities = model_data.get("modalities")
    plugin_modalities = plugin_profile.get("modalities")
    composed_modalities = _compose_modalities(plugin_modalities, model_modalities)
    if composed_modalities:
        base_profile["modalities"] = composed_modalities
    plugin_openai_capabilities = plugin_profile.get("openai_capabilities")
    model_openai_capabilities = model_data.get("openai_capabilities")
    composed_openai_capabilities = _compose_openai_capabilities(
        plugin_openai_capabilities,
        model_openai_capabilities,
    )
    if composed_openai_capabilities:
        base_profile["openai_capabilities"] = composed_openai_capabilities
    return base_profile


def _compose_modalities(
    plugin_modalities: JSONValue,
    model_modalities: JSONValue,
) -> list[str]:
    if not isinstance(plugin_modalities, list):
        return []
    normalized_plugin_modalities = normalize_openai_modalities_strict(
        [
            item.strip().lower()
            for item in plugin_modalities
            if isinstance(item, str) and item.strip()
        ],
        field_name="modalities",
    )
    if not isinstance(model_modalities, list):
        return list(normalized_plugin_modalities)
    normalized_model_modalities = normalize_openai_modalities_strict(
        [
            item.strip().lower()
            for item in model_modalities
            if isinstance(item, str) and item.strip()
        ],
        field_name="modalities",
    )
    narrowed_modalities = [
        modality
        for modality in normalized_plugin_modalities
        if modality in set(normalized_model_modalities)
    ]
    return narrowed_modalities


def _compose_openai_capabilities(
    plugin_openai_capabilities: JSONValue,
    model_openai_capabilities: JSONValue,
) -> JSONDict:
    normalized_plugin_openai_capabilities = normalize_openai_capabilities(
        plugin_openai_capabilities
    )
    if not isinstance(model_openai_capabilities, Mapping):
        return normalized_plugin_openai_capabilities
    normalized_model_openai_capabilities = normalize_openai_capabilities(
        dict(model_openai_capabilities)
    )
    return _narrow_openai_capabilities(
        normalized_plugin_openai_capabilities,
        normalized_model_openai_capabilities,
    )


def _narrow_openai_capabilities(
    plugin_openai_capabilities: JSONDict,
    model_openai_capabilities: JSONDict,
) -> JSONDict:
    narrowed: JSONDict = dict(plugin_openai_capabilities)
    for key, plugin_value in plugin_openai_capabilities.items():
        if key not in model_openai_capabilities:
            continue
        model_value = model_openai_capabilities[key]
        if isinstance(plugin_value, Mapping) and isinstance(model_value, Mapping):
            narrowed[key] = _narrow_openai_capabilities(
                dict(plugin_value),
                dict(model_value),
            )
            continue
        if isinstance(plugin_value, list) and isinstance(model_value, list):
            narrowed[key] = [
                item for item in plugin_value if isinstance(item, str) and item in set(model_value)
            ]
            continue
        if isinstance(plugin_value, bool) and isinstance(model_value, bool):
            narrowed[key] = plugin_value and model_value
            continue
        if not plugin_value:
            narrowed[key] = plugin_value
            continue
        narrowed[key] = model_value
    return narrowed


def resolve_effective_openai_profile(
    *,
    model_id: str,
    base_profile: JSONDict,
    overrides: JSONValue,
) -> JSONDict:
    try:
        effective_modalities, effective_caps = compute_effective_openai_model_profile(
            base_modalities=base_profile.get("modalities"),
            base_openai_capabilities=base_profile.get("openai_capabilities"),
            overrides=overrides,
        )
    except ValidationError as error:
        raise ValidationError(
            f"Model '{model_id}' has an invalid OpenAI capability profile.",
        ) from error
    return {
        "modalities": list(effective_modalities),
        "openai_capabilities": dict(effective_caps),
    }


def build_virtual_openai_profile(constituent_profiles: list[JSONDict]) -> JSONDict | None:
    modality_tokens: list[str] = []
    merged_capabilities: JSONDict = {}
    for profile in constituent_profiles:
        modalities_value = profile.get("modalities")
        if isinstance(modalities_value, list):
            for item in modalities_value:
                if isinstance(item, str) and item.strip():
                    modality_tokens.append(item.strip().lower())
        capabilities_value = profile.get("openai_capabilities")
        if isinstance(capabilities_value, Mapping):
            _merge_openai_capabilities(
                merged_capabilities,
                normalize_openai_capabilities(dict(capabilities_value)),
            )
    payload: JSONDict = {}
    if modality_tokens:
        payload["modalities"] = normalize_openai_modalities_strict(
            list(dict.fromkeys(modality_tokens)),
            field_name="modalities",
        )
    if merged_capabilities:
        payload["openai_capabilities"] = merged_capabilities
    return payload or None


def _merge_openai_capabilities(target: JSONDict, incoming: Mapping[str, JSONValue]) -> None:
    for key, value in incoming.items():
        if not isinstance(key, str) or not key or key == "modalities":
            continue
        if isinstance(value, Mapping):
            existing_value = target.get(key)
            nested_target: JSONDict = {}
            if isinstance(existing_value, Mapping):
                nested_target = dict(existing_value)
            _merge_openai_capabilities(nested_target, value)
            if nested_target:
                target[key] = nested_target
            continue
        if isinstance(value, list):
            continue
        enabled = coerce_bool_with_default(value, default=False, strict=True)
        if not enabled:
            continue
        target[key] = True

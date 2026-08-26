"""SoAI - Shared plugin manifest normalization helpers [backend/plugins/manifest/normalized_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.models.model_type_normalization import normalize_model_type_tokens
from core.openai.capability_taxonomy import OPENAI_FEATURE_MATRIX
from core.openai.compatibility import (
    ExternalProviderMode,
    normalize_external_provider_mode,
    normalize_openai_modalities_strict,
)
from core.types.json import is_json_dict
from core.validation.string_sequences import normalize_strict_string_sequence
from core.validation.strings import coerce_required_non_empty_str
from plugins.manifest.external_provider_support import resolve_external_provider_support

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_dependency_payload",
    "build_openai_capability_payload",
    "has_local_model_surfaces",
    "normalize_external_provider_defaults",
    "normalize_model_types",
    "normalize_optional_string_field",
    "normalize_required_non_empty_string_field",
    "normalize_required_string_field",
    "normalize_required_system_capabilities",
    "normalize_supports_backend_process_tracking",
    "normalize_supports_external_providers",
)


def normalize_required_string_field(value: JSONValue, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"Field '{field_name}' must be a string.")
    return value


def normalize_required_non_empty_string_field(value: JSONValue, *, field_name: str) -> str:
    return coerce_required_non_empty_str(value, label=f"Field '{field_name}'")


def normalize_optional_string_field(value: JSONValue, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"Field '{field_name}' must be a string or null.")
    return value


def build_dependency_payload(
    plugin_dependencies: list[str],
    package_dependencies: list[str],
) -> JSONDict:
    return {
        "plugins": list(plugin_dependencies),
        "packages": list(package_dependencies),
    }


def normalize_supports_backend_process_tracking(
    supports_backend_installation: bool,
    supports_backend_process_tracking: bool,
    *,
    plugin_name: str,
) -> bool:
    if supports_backend_process_tracking and (not supports_backend_installation):
        raise ValidationError(
            "Plugin contract violation: SUPPORTS_BACKEND_PROCESS_TRACKING=True requires SUPPORTS_BACKEND_INSTALLATION=True.",
            details={"plugin_name": plugin_name},
        )
    return supports_backend_installation and supports_backend_process_tracking


def normalize_supports_external_providers(
    provider_mode_value: ExternalProviderMode | str | Enum | None,
    supports_external_providers: bool,
) -> tuple[ExternalProviderMode, bool]:
    provider_mode = normalize_external_provider_mode(provider_mode_value)
    return (
        provider_mode,
        resolve_external_provider_support(provider_mode, supports_external_providers),
    )


def has_local_model_surfaces(
    *,
    local_resources: bool,
    local_models: bool,
    supports_backend_installation: bool,
    supports_model_download: bool,
) -> bool:
    return (
        local_resources or local_models or supports_backend_installation or supports_model_download
    )


def normalize_model_types(
    value: JSONValue,
    *,
    field_name: str,
    supports_external_providers: bool,
    external_provider_only: bool = True,
) -> list[str]:
    if supports_external_providers and external_provider_only:
        return ["external"]
    items = normalize_strict_string_sequence(value, field_name=field_name)
    normalized = list(normalize_model_type_tokens(items))
    if supports_external_providers and "external" not in normalized:
        normalized.append("external")
    return normalized


def normalize_external_provider_defaults(value: JSONValue) -> JSONDict:
    if value is None:
        return {}
    if not is_json_dict(value):
        raise ValidationError("Plugin external provider defaults must be a JSON object.")
    return dict(value)


def normalize_required_system_capabilities(value: JSONValue) -> JSONDict:
    if not is_json_dict(value):
        return {}
    return dict(value)


def build_openai_capability_payload(
    flag_values: Mapping[str, bool],
    *,
    modalities: list[str],
) -> JSONDict:
    payload: JSONDict = {}
    for section_name, entries in OPENAI_FEATURE_MATRIX:
        section_payload: JSONDict = {}
        for token, attr_name in entries:
            enabled = bool(flag_values.get(attr_name, False))
            section_payload[token] = enabled
            payload[token] = enabled
        payload[section_name] = section_payload
    payload["modalities"] = list(
        normalize_openai_modalities_strict(
            list(modalities),
            field_name="SUPPORTED_MODALITIES",
        ),
    )
    return payload

"""SoAI - Canonical plugin manifest payload construction [backend/plugins/manifest/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from core.errors.exceptions import SecurityError, ValidationError
from core.openai.compatibility import ExternalProviderMode
from core.plugins.backend_variant_option_validation import (
    require_backend_variant_options,
)
from core.types.json import is_json_dict
from core.validation.string_sequences import normalize_strict_string_sequence
from plugins.manifest.normalized_fields import (
    build_dependency_payload,
    build_openai_capability_payload,
    has_local_model_surfaces,
    normalize_external_provider_defaults,
    normalize_model_types,
    normalize_optional_string_field,
    normalize_required_non_empty_string_field,
    normalize_required_string_field,
    normalize_required_system_capabilities,
    normalize_supports_backend_process_tracking,
    normalize_supports_external_providers,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "PluginManifestPayloadSource",
    "build_plugin_manifest_payload",
)


@dataclass(frozen=True, slots=True)
class PluginManifestPayloadSource:
    plugin_name: str
    name: JSONValue
    version_soaiplugin: JSONValue
    author_soaiplugin: JSONValue
    description_soaiplugin: JSONValue
    website_soaiplugin: JSONValue
    license_soaiplugin: JSONValue
    website_backend: JSONValue
    license_managed_backend: JSONValue
    model_repository: JSONValue
    model_types: JSONValue
    required_soai_version: JSONValue
    aliases: JSONValue
    plugin_dependencies: JSONValue
    package_dependencies: JSONValue
    supported_modalities: JSONValue
    local_resources: bool
    local_models: bool
    persistent: bool
    max_concurrent_requests: JSONValue
    supports_backend_installation: bool
    supports_backend_process_tracking: bool
    supports_model_deletion: bool
    supports_model_download: bool
    supports_configuration: bool
    supports_gpu_binding: bool
    supports_external_providers: bool
    external_provider_mode: ExternalProviderMode | str | Enum | None
    supports_cloning: bool
    required_system_capabilities: JSONValue
    openai_flag_values: Mapping[str, bool]
    openai_capabilities_override: JSONDict | None = None
    class_name: str | None = None
    external_provider_defaults: JSONValue = None
    default_configuration: JSONValue = None
    parameter_schema: JSONValue = None
    backend_variant_options: JSONValue = None
    supports_model_search: bool = False
    supports_model_variant_discovery: bool = False
    supports_prompt_token_counting: bool = False


def _resolve_openai_capability_payload(source: PluginManifestPayloadSource) -> JSONDict:
    modalities = normalize_strict_string_sequence(
        source.supported_modalities,
        field_name="SUPPORTED_MODALITIES",
    )
    if source.openai_capabilities_override is not None:
        payload = source.openai_capabilities_override
        if not is_json_dict(payload):
            raise ValidationError("Plugin OpenAI capabilities payload must be a JSON object.")
        return dict(payload)
    return build_openai_capability_payload(source.openai_flag_values, modalities=modalities)


def build_plugin_manifest_payload(source: PluginManifestPayloadSource) -> JSONDict:
    provider_mode, supports_external_providers = normalize_supports_external_providers(
        source.external_provider_mode,
        source.supports_external_providers,
    )
    modalities = normalize_strict_string_sequence(
        source.supported_modalities,
        field_name="SUPPORTED_MODALITIES",
    )
    openai_capabilities = _resolve_openai_capability_payload(source)
    modality_payload = build_openai_capability_payload({}, modalities=modalities)
    normalized_modalities_value = modality_payload.get("modalities")
    normalized_modalities = (
        list(normalized_modalities_value) if isinstance(normalized_modalities_value, list) else []
    )
    license_managed_backend = normalize_optional_string_field(
        source.license_managed_backend,
        field_name="LICENSE_MANAGED_BACKEND",
    )
    if source.supports_backend_installation and not license_managed_backend:
        raise ValidationError(
            "Manifest field 'LICENSE_MANAGED_BACKEND' must be set when backend installation is supported.",
        )
    payload: JSONDict = {
        "plugin_name": source.plugin_name,
        "name": normalize_required_non_empty_string_field(source.name, field_name="NAME"),
        "version_soaiplugin": normalize_required_non_empty_string_field(
            source.version_soaiplugin,
            field_name="VERSION_SOAIPLUGIN",
        ),
        "author_soaiplugin": normalize_required_string_field(
            source.author_soaiplugin,
            field_name="AUTHOR_SOAIPLUGIN",
        ),
        "description_soaiplugin": normalize_required_string_field(
            source.description_soaiplugin,
            field_name="DESCRIPTION_SOAIPLUGIN",
        ),
        "website_soaiplugin": normalize_required_string_field(
            source.website_soaiplugin,
            field_name="WEBSITE_SOAIPLUGIN",
        ),
        "license_soaiplugin": normalize_required_non_empty_string_field(
            source.license_soaiplugin,
            field_name="LICENSE_SOAIPLUGIN",
        ),
        "website_backend": normalize_optional_string_field(
            source.website_backend,
            field_name="WEBSITE_BACKEND",
        ),
        "license_managed_backend": license_managed_backend,
        "core_compat": normalize_required_non_empty_string_field(
            source.required_soai_version,
            field_name="REQUIRED_SOAI_VERSION",
        ),
        "aliases": normalize_strict_string_sequence(source.aliases, field_name="ALIASES"),
        "dependencies": build_dependency_payload(
            normalize_strict_string_sequence(
                source.plugin_dependencies,
                field_name="PLUGIN_DEPENDENCIES",
            ),
            normalize_strict_string_sequence(
                source.package_dependencies,
                field_name="PACKAGE_DEPENDENCIES",
            ),
        ),
        "modalities": normalized_modalities,
        "supports_backend_installation": source.supports_backend_installation,
        "supports_backend_process_tracking": normalize_supports_backend_process_tracking(
            source.supports_backend_installation,
            source.supports_backend_process_tracking,
            plugin_name=source.plugin_name,
        ),
        "supports_model_deletion": source.supports_model_deletion,
        "supports_model_download": source.supports_model_download,
        "has_configuration": source.supports_configuration,
        "supports_gpu_binding": source.supports_gpu_binding,
        "supports_external_providers": supports_external_providers,
        "external_provider_mode": provider_mode.value,
        "external_provider_defaults": normalize_external_provider_defaults(
            source.external_provider_defaults,
        ),
        "persistent": source.persistent,
        "max_concurrent_requests": source.max_concurrent_requests,
        "local_resources": source.local_resources,
        "local_models": source.local_models,
        "supports_cloning": source.supports_cloning,
        "model_repository": normalize_optional_string_field(
            source.model_repository,
            field_name="MODEL_REPOSITORY",
        ),
        "model_types": normalize_model_types(
            source.model_types,
            field_name="MODEL_TYPES",
            supports_external_providers=supports_external_providers,
            external_provider_only=not has_local_model_surfaces(
                local_resources=source.local_resources,
                local_models=source.local_models,
                supports_backend_installation=source.supports_backend_installation,
                supports_model_download=source.supports_model_download,
            ),
        ),
        "required_system_capabilities": normalize_required_system_capabilities(
            source.required_system_capabilities,
        ),
        "openai_capabilities": openai_capabilities,
        "default_configuration": (
            dict(source.default_configuration) if is_json_dict(source.default_configuration) else {}
        ),
        "parameter_schema": (
            dict(source.parameter_schema) if is_json_dict(source.parameter_schema) else {}
        ),
        "backend_variant_options": require_backend_variant_options(
            source.backend_variant_options,
            field_name="BACKEND_VARIANT_OPTIONS",
        ),
        "supports_model_search": source.supports_model_search,
        "supports_model_variant_discovery": source.supports_model_variant_discovery,
        "supports_prompt_token_counting": source.supports_prompt_token_counting,
        "runtime_loaded": False,
    }
    if source.class_name is not None:
        payload["class_name"] = source.class_name
    if not is_json_dict(payload):
        raise SecurityError("Internal error: plugin manifest payload is not a JSON object.")
    return payload

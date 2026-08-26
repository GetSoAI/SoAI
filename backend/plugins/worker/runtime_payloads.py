"""SoAI - Plugin worker runtime payload helpers [backend/plugins/worker/runtime_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from core.errors.exceptions import ValidationError
from core.plugins.base_plugin import BasePlugin
from core.plugins.protocols_instance import ClonableFieldProtocol
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict, JSONValue, is_json_value
from plugins.manifest.class_field_contract import (
    PLUGIN_FIELD_ALIASES,
    PLUGIN_FIELD_AUTHOR_SOAIPLUGIN,
    PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS,
    PLUGIN_FIELD_CLONABLE_FIELDS,
    PLUGIN_FIELD_DEFAULT_CONFIGURATION,
    PLUGIN_FIELD_DESCRIPTION_SOAIPLUGIN,
    PLUGIN_FIELD_EXTERNAL_PROVIDER_DEFAULTS,
    PLUGIN_FIELD_EXTERNAL_PROVIDER_MODE,
    PLUGIN_FIELD_LICENSE_MANAGED_BACKEND,
    PLUGIN_FIELD_LICENSE_SOAIPLUGIN,
    PLUGIN_FIELD_LOCAL_MODELS,
    PLUGIN_FIELD_LOCAL_RESOURCES,
    PLUGIN_FIELD_MAX_CONCURRENT_REQUESTS,
    PLUGIN_FIELD_MODEL_REPOSITORY,
    PLUGIN_FIELD_MODEL_TYPES,
    PLUGIN_FIELD_NAME,
    PLUGIN_FIELD_PACKAGE_DEPENDENCIES,
    PLUGIN_FIELD_PERSISTENT,
    PLUGIN_FIELD_PLUGIN_DEPENDENCIES,
    PLUGIN_FIELD_REQUIRED_SOAI_VERSION,
    PLUGIN_FIELD_REQUIRED_SYSTEM_CAPABILITIES,
    PLUGIN_FIELD_SUPPORTED_MODALITIES,
    PLUGIN_FIELD_SUPPORTS_BACKEND_INSTALLATION,
    PLUGIN_FIELD_SUPPORTS_BACKEND_PROCESS_TRACKING,
    PLUGIN_FIELD_SUPPORTS_CLONING,
    PLUGIN_FIELD_SUPPORTS_CONFIGURATION,
    PLUGIN_FIELD_SUPPORTS_EXTERNAL_PROVIDERS,
    PLUGIN_FIELD_SUPPORTS_GPU_BINDING,
    PLUGIN_FIELD_SUPPORTS_MODEL_DELETION,
    PLUGIN_FIELD_SUPPORTS_MODEL_DOWNLOAD,
    PLUGIN_FIELD_SUPPORTS_MODEL_SEARCH,
    PLUGIN_FIELD_SUPPORTS_MODEL_VARIANT_DISCOVERY,
    PLUGIN_FIELD_SUPPORTS_PROMPT_TOKEN_COUNTING,
    PLUGIN_FIELD_VERSION_SOAIPLUGIN,
    PLUGIN_FIELD_WEBSITE_BACKEND,
    PLUGIN_FIELD_WEBSITE_SOAIPLUGIN,
    PLUGIN_FIELD_WELCOME_MESSAGE,
)
from plugins.worker.payload_fields import (
    read_bool_field,
    read_dict_field,
    read_number_field,
)
from plugins.worker.runtime_adapters import WorkerRuntimeFlags

__all__ = (
    "class_fields",
    "runtime_flags_from_bootstrap",
    "update_runtime_flags_from_payload",
)


def class_fields(plugin_class: type[BasePlugin]) -> JSONDict:
    provider_mode = plugin_class.EXTERNAL_PROVIDER_MODE
    clonable_fields: list[JSONDict] = []
    for field in plugin_class.CLONABLE_FIELDS:
        clonable_fields.append(_clonable_field_payload(field))
    return {
        PLUGIN_FIELD_NAME: _json_field(plugin_class.NAME),
        PLUGIN_FIELD_AUTHOR_SOAIPLUGIN: _json_field(plugin_class.AUTHOR_SOAIPLUGIN),
        PLUGIN_FIELD_DESCRIPTION_SOAIPLUGIN: _json_field(
            plugin_class.DESCRIPTION_SOAIPLUGIN,
        ),
        PLUGIN_FIELD_WEBSITE_SOAIPLUGIN: _json_field(plugin_class.WEBSITE_SOAIPLUGIN),
        PLUGIN_FIELD_VERSION_SOAIPLUGIN: _json_field(plugin_class.VERSION_SOAIPLUGIN),
        PLUGIN_FIELD_LICENSE_SOAIPLUGIN: _json_field(plugin_class.LICENSE_SOAIPLUGIN),
        PLUGIN_FIELD_REQUIRED_SOAI_VERSION: _json_field(plugin_class.REQUIRED_SOAI_VERSION),
        PLUGIN_FIELD_MODEL_REPOSITORY: _json_field(plugin_class.MODEL_REPOSITORY),
        PLUGIN_FIELD_MODEL_TYPES: _json_field(plugin_class.MODEL_TYPES),
        PLUGIN_FIELD_WEBSITE_BACKEND: _json_field(plugin_class.WEBSITE_BACKEND),
        PLUGIN_FIELD_LICENSE_MANAGED_BACKEND: _json_field(plugin_class.LICENSE_MANAGED_BACKEND),
        PLUGIN_FIELD_MAX_CONCURRENT_REQUESTS: _json_field(plugin_class.MAX_CONCURRENT_REQUESTS),
        PLUGIN_FIELD_REQUIRED_SYSTEM_CAPABILITIES: _json_field(
            normalize_for_json(dict(plugin_class.REQUIRED_SYSTEM_CAPABILITIES)),
        ),
        PLUGIN_FIELD_DEFAULT_CONFIGURATION: _json_field(
            normalize_for_json(dict(plugin_class.DEFAULT_CONFIGURATION)),
        ),
        PLUGIN_FIELD_ALIASES: _json_field(plugin_class.ALIASES),
        PLUGIN_FIELD_PLUGIN_DEPENDENCIES: _json_field(plugin_class.PLUGIN_DEPENDENCIES),
        PLUGIN_FIELD_PACKAGE_DEPENDENCIES: _json_field(plugin_class.PACKAGE_DEPENDENCIES),
        PLUGIN_FIELD_LOCAL_RESOURCES: _json_field(plugin_class.LOCAL_RESOURCES),
        PLUGIN_FIELD_LOCAL_MODELS: _json_field(plugin_class.LOCAL_MODELS),
        PLUGIN_FIELD_PERSISTENT: _json_field(plugin_class.PERSISTENT),
        PLUGIN_FIELD_SUPPORTS_BACKEND_INSTALLATION: _json_field(
            plugin_class.SUPPORTS_BACKEND_INSTALLATION,
        ),
        PLUGIN_FIELD_SUPPORTS_BACKEND_PROCESS_TRACKING: _json_field(
            plugin_class.SUPPORTS_BACKEND_PROCESS_TRACKING,
        ),
        PLUGIN_FIELD_SUPPORTS_CONFIGURATION: _json_field(plugin_class.SUPPORTS_CONFIGURATION),
        PLUGIN_FIELD_SUPPORTS_GPU_BINDING: _json_field(plugin_class.SUPPORTS_GPU_BINDING),
        PLUGIN_FIELD_SUPPORTS_PROMPT_TOKEN_COUNTING: _json_field(
            plugin_class.SUPPORTS_PROMPT_TOKEN_COUNTING,
        ),
        PLUGIN_FIELD_SUPPORTS_MODEL_VARIANT_DISCOVERY: _json_field(
            plugin_class.SUPPORTS_MODEL_VARIANT_DISCOVERY,
        ),
        PLUGIN_FIELD_SUPPORTS_MODEL_DELETION: _json_field(
            plugin_class.SUPPORTS_MODEL_DELETION,
        ),
        PLUGIN_FIELD_SUPPORTS_MODEL_DOWNLOAD: _json_field(plugin_class.SUPPORTS_MODEL_DOWNLOAD),
        PLUGIN_FIELD_SUPPORTS_MODEL_SEARCH: _json_field(plugin_class.SUPPORTS_MODEL_SEARCH),
        PLUGIN_FIELD_SUPPORTS_CLONING: _json_field(plugin_class.SUPPORTS_CLONING),
        PLUGIN_FIELD_SUPPORTS_EXTERNAL_PROVIDERS: _json_field(
            plugin_class.SUPPORTS_EXTERNAL_PROVIDERS,
        ),
        PLUGIN_FIELD_EXTERNAL_PROVIDER_DEFAULTS: _json_field(
            normalize_for_json(dict(plugin_class.EXTERNAL_PROVIDER_DEFAULTS)),
        ),
        PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS: _json_field(
            normalize_for_json(list(plugin_class.BACKEND_VARIANT_OPTIONS)),
        ),
        PLUGIN_FIELD_SUPPORTED_MODALITIES: _json_field(list(plugin_class.SUPPORTED_MODALITIES)),
        PLUGIN_FIELD_CLONABLE_FIELDS: _json_field(clonable_fields),
        PLUGIN_FIELD_WELCOME_MESSAGE: _json_field(plugin_class.WELCOME_MESSAGE),
        PLUGIN_FIELD_EXTERNAL_PROVIDER_MODE: (
            provider_mode.value if isinstance(provider_mode, Enum) else str(provider_mode)
        ),
    }


def runtime_flags_from_bootstrap(payload: JSONDict) -> WorkerRuntimeFlags:
    flags = read_dict_field(payload, "runtime_flags", label="Worker request field")
    (
        host_system_actions_disabled,
        hardware_mutation_disabled,
        offline_mode,
        block_private_network_egress,
        dns_validation_timeout_sec,
        host_management_available,
    ) = _read_runtime_flags_values(flags)
    return WorkerRuntimeFlags(
        host_system_actions_disabled=host_system_actions_disabled,
        hardware_mutation_disabled=hardware_mutation_disabled,
        offline_mode=offline_mode,
        block_private_network_egress=block_private_network_egress,
        dns_validation_timeout_sec=dns_validation_timeout_sec,
        host_management_available=host_management_available,
    )


def update_runtime_flags_from_payload(runtime_flags: WorkerRuntimeFlags, payload: JSONDict) -> None:
    flags = read_dict_field(payload, "runtime_flags", label="Worker request field")
    (
        host_system_actions_disabled,
        hardware_mutation_disabled,
        offline_mode,
        block_private_network_egress,
        dns_validation_timeout_sec,
        host_management_available,
    ) = _read_runtime_flags_values(flags)
    runtime_flags.update_runtime_policy(
        host_system_actions_disabled=host_system_actions_disabled,
        hardware_mutation_disabled=hardware_mutation_disabled,
        offline_mode=offline_mode,
        block_private_network_egress=block_private_network_egress,
        dns_validation_timeout_sec=dns_validation_timeout_sec,
        host_management_available=host_management_available,
    )


def _read_runtime_flags_values(
    flags: JSONDict,
) -> tuple[bool, bool, bool, bool, float, bool]:
    return (
        read_bool_field(
            flags,
            "host_system_actions_disabled",
            label="Worker request field",
        ),
        read_bool_field(
            flags,
            "hardware_mutation_disabled",
            label="Worker request field",
        ),
        read_bool_field(flags, "offline_mode", label="Worker request field"),
        read_bool_field(
            flags,
            "block_private_network_egress",
            label="Worker request field",
        ),
        float(read_number_field(flags, "dns_validation_timeout_sec", label="Worker request field")),
        read_bool_field(flags, "host_management_available", label="Worker request field"),
    )


def _clonable_field_payload(field: ClonableFieldProtocol) -> JSONDict:
    name = field.get("name")
    display_name = field.get("display_name")
    field_type = field.get("field_type")
    required = field.get("required")
    if (
        not isinstance(name, str)
        or not isinstance(display_name, str)
        or field_type not in {"port", "path", "string"}
        or not isinstance(required, bool)
    ):
        raise ValidationError("Plugin CLONABLE_FIELDS contains a malformed field.")
    return {
        "name": name,
        "display_name": display_name,
        "field_type": field_type,
        "required": required,
    }


def _json_field(value: JSONValue | tuple[str, ...] | None) -> JSONValue:
    if isinstance(value, tuple):
        items = list(value)
        if not all(is_json_value(item) for item in items):
            raise ValidationError("Plugin class tuple field contains a non-JSON value.")
        return items
    if not is_json_value(value):
        raise ValidationError("Plugin class field contains a non-JSON value.")
    return value

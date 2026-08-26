"""SoAI - Proxy plugin surface field assignment [backend/plugins/worker/proxy_surface_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from plugins.manifest.class_field_contract import (
    PLUGIN_FIELD_ALIASES,
    PLUGIN_FIELD_AUTHOR_SOAIPLUGIN,
    PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS,
    PLUGIN_FIELD_DEFAULT_CONFIGURATION,
    PLUGIN_FIELD_DESCRIPTION_SOAIPLUGIN,
    PLUGIN_FIELD_EXTERNAL_PROVIDER_DEFAULTS,
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
from plugins.worker.internal_protocols import ProxySurfaceTarget
from plugins.worker.proxy_surface_readers import (
    read_bool_surface_field,
    read_clonable_surface_fields,
    read_int_surface_field,
    read_json_dict_list_surface_field,
    read_mapping_surface_field,
    read_optional_str_surface_field,
    read_provider_mode_surface_field,
    read_str_surface_field,
    read_string_tuple_surface_field,
)
from plugins.worker.surface import PluginRuntimeSurface

__all__ = (
    "ProxySurfaceTarget",
    "apply_proxy_surface_fields",
)


def apply_proxy_surface_fields(
    target: ProxySurfaceTarget,
    surface: PluginRuntimeSurface,
) -> None:
    target.NAME = read_str_surface_field(surface, PLUGIN_FIELD_NAME)
    target.AUTHOR_SOAIPLUGIN = read_str_surface_field(
        surface,
        PLUGIN_FIELD_AUTHOR_SOAIPLUGIN,
    )
    target.DESCRIPTION_SOAIPLUGIN = read_str_surface_field(
        surface, PLUGIN_FIELD_DESCRIPTION_SOAIPLUGIN
    )
    target.WEBSITE_SOAIPLUGIN = read_str_surface_field(surface, PLUGIN_FIELD_WEBSITE_SOAIPLUGIN)
    target.VERSION_SOAIPLUGIN = read_str_surface_field(surface, PLUGIN_FIELD_VERSION_SOAIPLUGIN)
    target.LICENSE_SOAIPLUGIN = read_str_surface_field(surface, PLUGIN_FIELD_LICENSE_SOAIPLUGIN)
    target.REQUIRED_SOAI_VERSION = read_str_surface_field(
        surface, PLUGIN_FIELD_REQUIRED_SOAI_VERSION
    )
    target.MODEL_REPOSITORY = read_optional_str_surface_field(
        surface, PLUGIN_FIELD_MODEL_REPOSITORY
    )
    target.MODEL_TYPES = read_string_tuple_surface_field(
        surface,
        PLUGIN_FIELD_MODEL_TYPES,
    )
    target.WEBSITE_BACKEND = read_optional_str_surface_field(surface, PLUGIN_FIELD_WEBSITE_BACKEND)
    target.LICENSE_MANAGED_BACKEND = read_optional_str_surface_field(
        surface,
        PLUGIN_FIELD_LICENSE_MANAGED_BACKEND,
    )
    target.MAX_CONCURRENT_REQUESTS = read_int_surface_field(
        surface, PLUGIN_FIELD_MAX_CONCURRENT_REQUESTS
    )
    target.REQUIRED_SYSTEM_CAPABILITIES = read_mapping_surface_field(
        surface,
        PLUGIN_FIELD_REQUIRED_SYSTEM_CAPABILITIES,
    )
    target.DEFAULT_CONFIGURATION = read_mapping_surface_field(
        surface, PLUGIN_FIELD_DEFAULT_CONFIGURATION
    )
    target.ALIASES = read_string_tuple_surface_field(surface, PLUGIN_FIELD_ALIASES)
    target.PLUGIN_DEPENDENCIES = read_string_tuple_surface_field(
        surface, PLUGIN_FIELD_PLUGIN_DEPENDENCIES
    )
    target.PACKAGE_DEPENDENCIES = read_string_tuple_surface_field(
        surface, PLUGIN_FIELD_PACKAGE_DEPENDENCIES
    )
    target.LOCAL_RESOURCES = read_bool_surface_field(surface, PLUGIN_FIELD_LOCAL_RESOURCES)
    target.LOCAL_MODELS = read_bool_surface_field(surface, PLUGIN_FIELD_LOCAL_MODELS)
    target.PERSISTENT = read_bool_surface_field(surface, PLUGIN_FIELD_PERSISTENT)
    target.SUPPORTS_BACKEND_INSTALLATION = read_bool_surface_field(
        surface,
        PLUGIN_FIELD_SUPPORTS_BACKEND_INSTALLATION,
    )
    target.SUPPORTS_BACKEND_PROCESS_TRACKING = read_bool_surface_field(
        surface,
        PLUGIN_FIELD_SUPPORTS_BACKEND_PROCESS_TRACKING,
    )
    target.SUPPORTS_CONFIGURATION = read_bool_surface_field(
        surface, PLUGIN_FIELD_SUPPORTS_CONFIGURATION
    )
    target.SUPPORTS_GPU_BINDING = read_bool_surface_field(
        surface, PLUGIN_FIELD_SUPPORTS_GPU_BINDING
    )
    target.SUPPORTS_PROMPT_TOKEN_COUNTING = read_bool_surface_field(
        surface,
        PLUGIN_FIELD_SUPPORTS_PROMPT_TOKEN_COUNTING,
    )
    target.SUPPORTS_MODEL_VARIANT_DISCOVERY = read_bool_surface_field(
        surface,
        PLUGIN_FIELD_SUPPORTS_MODEL_VARIANT_DISCOVERY,
    )
    target.SUPPORTS_MODEL_DELETION = read_bool_surface_field(
        surface, PLUGIN_FIELD_SUPPORTS_MODEL_DELETION
    )
    target.SUPPORTS_MODEL_DOWNLOAD = read_bool_surface_field(
        surface, PLUGIN_FIELD_SUPPORTS_MODEL_DOWNLOAD
    )
    target.SUPPORTS_MODEL_SEARCH = read_bool_surface_field(
        surface, PLUGIN_FIELD_SUPPORTS_MODEL_SEARCH
    )
    target.SUPPORTS_CLONING = read_bool_surface_field(surface, PLUGIN_FIELD_SUPPORTS_CLONING)
    target.SUPPORTS_EXTERNAL_PROVIDERS = read_bool_surface_field(
        surface,
        PLUGIN_FIELD_SUPPORTS_EXTERNAL_PROVIDERS,
    )
    target.EXTERNAL_PROVIDER_MODE = read_provider_mode_surface_field(surface)
    target.EXTERNAL_PROVIDER_DEFAULTS = read_mapping_surface_field(
        surface,
        PLUGIN_FIELD_EXTERNAL_PROVIDER_DEFAULTS,
    )
    target.BACKEND_VARIANT_OPTIONS = read_json_dict_list_surface_field(
        surface,
        PLUGIN_FIELD_BACKEND_VARIANT_OPTIONS,
    )
    target.SUPPORTED_MODALITIES = read_string_tuple_surface_field(
        surface, PLUGIN_FIELD_SUPPORTED_MODALITIES
    )
    target.CLONABLE_FIELDS = read_clonable_surface_fields(surface)
    target.WELCOME_MESSAGE = read_optional_str_surface_field(
        surface,
        PLUGIN_FIELD_WELCOME_MESSAGE,
    )

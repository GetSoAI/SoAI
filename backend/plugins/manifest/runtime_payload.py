"""SoAI - Runtime plugin manifest payload construction [backend/plugins/manifest/runtime_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.protocols_instance import PluginInstanceProtocol
from core.types.json import JSONDict
from plugins.manifest.payloads import (
    PluginManifestPayloadSource,
    build_plugin_manifest_payload,
)

__all__ = ("build_runtime_plugin_manifest_payload",)


async def build_runtime_plugin_manifest_payload(
    instance: PluginInstanceProtocol,
    *,
    default_configuration: JSONDict | None = None,
    parameter_schema: JSONDict | None = None,
) -> JSONDict:
    resolved_default_configuration = (
        dict(default_configuration)
        if default_configuration is not None
        else dict(instance.DEFAULT_CONFIGURATION)
    )
    resolved_parameter_schema = (
        dict(parameter_schema)
        if parameter_schema is not None
        else await instance.get_parameter_schema()
    )
    payload = build_plugin_manifest_payload(
        PluginManifestPayloadSource(
            plugin_name=instance.plugin_name,
            name=instance.NAME,
            version_soaiplugin=instance.VERSION_SOAIPLUGIN,
            author_soaiplugin=instance.AUTHOR_SOAIPLUGIN,
            description_soaiplugin=instance.DESCRIPTION_SOAIPLUGIN,
            website_soaiplugin=instance.WEBSITE_SOAIPLUGIN,
            license_soaiplugin=instance.LICENSE_SOAIPLUGIN,
            website_backend=instance.WEBSITE_BACKEND,
            license_managed_backend=instance.LICENSE_MANAGED_BACKEND,
            model_repository=instance.MODEL_REPOSITORY,
            model_types=list(instance.MODEL_TYPES),
            required_soai_version=instance.REQUIRED_SOAI_VERSION,
            aliases=list(instance.ALIASES),
            plugin_dependencies=list(instance.PLUGIN_DEPENDENCIES),
            package_dependencies=list(instance.PACKAGE_DEPENDENCIES),
            supported_modalities=list(instance.SUPPORTED_MODALITIES),
            local_resources=instance.LOCAL_RESOURCES,
            local_models=instance.LOCAL_MODELS,
            persistent=instance.PERSISTENT,
            max_concurrent_requests=instance.MAX_CONCURRENT_REQUESTS,
            supports_backend_installation=instance.SUPPORTS_BACKEND_INSTALLATION,
            supports_backend_process_tracking=instance.SUPPORTS_BACKEND_PROCESS_TRACKING,
            supports_model_deletion=instance.SUPPORTS_MODEL_DELETION,
            supports_model_download=instance.SUPPORTS_MODEL_DOWNLOAD,
            supports_configuration=instance.SUPPORTS_CONFIGURATION,
            supports_gpu_binding=instance.SUPPORTS_GPU_BINDING,
            supports_external_providers=instance.SUPPORTS_EXTERNAL_PROVIDERS,
            external_provider_mode=instance.EXTERNAL_PROVIDER_MODE,
            supports_cloning=instance.SUPPORTS_CLONING,
            required_system_capabilities=dict(instance.REQUIRED_SYSTEM_CAPABILITIES),
            openai_flag_values={},
            openai_capabilities_override=instance.openai_capabilities,
            external_provider_defaults=instance.EXTERNAL_PROVIDER_DEFAULTS,
            default_configuration=resolved_default_configuration,
            parameter_schema=resolved_parameter_schema,
            backend_variant_options=list(instance.BACKEND_VARIANT_OPTIONS),
            supports_model_search=instance.SUPPORTS_MODEL_SEARCH,
            supports_model_variant_discovery=instance.SUPPORTS_MODEL_VARIANT_DISCOVERY,
            supports_prompt_token_counting=instance.SUPPORTS_PROMPT_TOKEN_COUNTING,
        ),
    )
    payload["runtime_loaded"] = True
    return payload

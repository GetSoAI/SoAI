"""SoAI - Proxy plugin static surface defaults [backend/plugins/worker/proxy_static_surface.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from core.openai.compatibility import ExternalProviderMode
from core.plugins.protocols_instance import ClonableFieldProtocol
from core.types.json import JSONDict, JSONValue

__all__ = ("ProxyPluginStaticSurface",)


class ProxyPluginStaticSurface:
    NAME: str = ""
    AUTHOR_SOAIPLUGIN: str = ""
    DESCRIPTION_SOAIPLUGIN: str = ""
    WEBSITE_SOAIPLUGIN: str = ""
    VERSION_SOAIPLUGIN: str = ""
    LICENSE_SOAIPLUGIN: str = ""
    REQUIRED_SOAI_VERSION: str = ""
    MODEL_REPOSITORY: str | None = None
    MODEL_TYPES: tuple[str, ...] = ()
    WEBSITE_BACKEND: str | None = None
    LICENSE_MANAGED_BACKEND: str | None = None
    MAX_CONCURRENT_REQUESTS: int | None = None
    REQUIRED_SYSTEM_CAPABILITIES: Mapping[str, JSONValue] = MappingProxyType({})
    DEFAULT_CONFIGURATION: Mapping[str, JSONValue] = MappingProxyType({})
    ALIASES: tuple[str, ...] = ()
    PLUGIN_DEPENDENCIES: tuple[str, ...] = ()
    PACKAGE_DEPENDENCIES: tuple[str, ...] = ()
    LOCAL_RESOURCES: bool = False
    LOCAL_MODELS: bool = False
    PERSISTENT: bool = False
    SUPPORTS_BACKEND_INSTALLATION: bool = False
    SUPPORTS_BACKEND_PROCESS_TRACKING: bool = False
    SUPPORTS_CONFIGURATION: bool = False
    SUPPORTS_GPU_BINDING: bool = False
    SUPPORTS_PROMPT_TOKEN_COUNTING: bool = False
    SUPPORTS_MODEL_VARIANT_DISCOVERY: bool = False
    SUPPORTS_MODEL_DELETION: bool = False
    SUPPORTS_MODEL_DOWNLOAD: bool = False
    SUPPORTS_MODEL_SEARCH: bool = False
    SUPPORTS_CLONING: bool = False
    SUPPORTS_EXTERNAL_PROVIDERS: bool = False
    EXTERNAL_PROVIDER_MODE: ExternalProviderMode = ExternalProviderMode.NONE
    EXTERNAL_PROVIDER_DEFAULTS: Mapping[str, JSONValue] = MappingProxyType({})
    BACKEND_VARIANT_OPTIONS: Sequence[JSONDict] = ()
    SUPPORTED_MODALITIES: Sequence[str] = ()
    CLONABLE_FIELDS: tuple[ClonableFieldProtocol, ...] = ()
    WELCOME_MESSAGE: str | None = None

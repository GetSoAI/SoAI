"""SoAI - Core base plugin default capability flags and metadata [backend/core/plugins/base_plugin_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

from core.errors.exceptions import StateError
from core.meta.version import __version__
from core.openai.capability_taxonomy import (
    OPENAI_FEATURE_MATRIX,
    OpenAIModality,
)
from core.openai.compatibility import ExternalProviderMode
from core.plugins.protocols_instance import ClonableFieldProtocol
from core.plugins.request_capability_methods import (
    count_prompt_tokens_method,
    get_available_variants_method,
    handle_embedding_request_method,
    search_remote_models_method,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("BasePluginDefaults",)


class BasePluginDefaults:
    @classmethod
    def get_openai_capabilities(cls) -> JSONDict:
        raise StateError(f"Plugin class '{cls.__name__}' must define get_openai_capabilities().")

    @property
    def openai_capabilities(self) -> JSONDict:
        capabilities = type(self).get_openai_capabilities()
        if not isinstance(capabilities, dict):
            raise StateError("Plugin OpenAI capabilities must resolve to a dictionary.")
        return capabilities

    get_available_variants = get_available_variants_method
    count_prompt_tokens = count_prompt_tokens_method
    handle_embedding_request = handle_embedding_request_method
    search_remote_models = search_remote_models_method
    NAME: ClassVar[str] = "Unnamed Plugin"
    AUTHOR_SOAIPLUGIN: ClassVar[str] = "Unknown"
    DESCRIPTION_SOAIPLUGIN: ClassVar[str] = "No description provided."
    WELCOME_MESSAGE: ClassVar[str | None] = None
    WEBSITE_SOAIPLUGIN: ClassVar[str] = ""
    VERSION_SOAIPLUGIN: ClassVar[str] = "0.0.0"
    LICENSE_SOAIPLUGIN: ClassVar[str] = ""
    REQUIRED_SOAI_VERSION: ClassVar[str] = ">=1.0.0"
    MODEL_REPOSITORY: ClassVar[str | None] = None
    MODEL_TYPES: ClassVar[tuple[str, ...]] = ()
    WEBSITE_BACKEND: ClassVar[str | None] = None
    LICENSE_MANAGED_BACKEND: ClassVar[str | None] = None
    MAX_CONCURRENT_REQUESTS: ClassVar[int | None] = None
    PLUGIN_DEPENDENCIES: ClassVar[tuple[str, ...]] = ()
    PACKAGE_DEPENDENCIES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_SYSTEM_CAPABILITIES: ClassVar[Mapping[str, JSONValue]] = MappingProxyType({})
    DEFAULT_CONFIGURATION: ClassVar[Mapping[str, JSONValue]] = MappingProxyType({})
    ALIASES: ClassVar[tuple[str, ...]] = ()
    LOCAL_RESOURCES: ClassVar[bool] = False
    LOCAL_MODELS: ClassVar[bool] = False
    PERSISTENT: ClassVar[bool] = False
    SUPPORTS_BACKEND_INSTALLATION: ClassVar[bool] = False
    SUPPORTS_BACKEND_PROCESS_TRACKING: ClassVar[bool] = False
    SUPPORTS_MODEL_DOWNLOAD: ClassVar[bool] = False
    SUPPORTS_MODEL_DELETION: ClassVar[bool] = False
    SUPPORTS_CONFIGURATION: ClassVar[bool] = False
    SUPPORTS_GPU_BINDING: ClassVar[bool] = False
    SUPPORTS_PROMPT_TOKEN_COUNTING: ClassVar[bool] = False
    SUPPORTS_EXTERNAL_PROVIDERS: ClassVar[bool] = False
    SUPPORTS_EMBEDDINGS: ClassVar[bool] = False
    SUPPORTS_CHAT_COMPLETIONS: ClassVar[bool] = True
    SUPPORTS_COMPLETIONS: ClassVar[bool] = True
    SUPPORTS_MODEL_SEARCH: ClassVar[bool] = False
    SUPPORTS_RESPONSES: ClassVar[bool] = False
    EXTERNAL_PROVIDER_DEFAULTS: ClassVar[Mapping[str, JSONValue]] = MappingProxyType({})
    BACKEND_VARIANT_OPTIONS: ClassVar[Sequence[JSONDict]] = ()
    SUPPORTS_IMAGES: ClassVar[bool] = False
    SUPPORTS_IMAGE_EDITS: ClassVar[bool] = False
    SUPPORTS_IMAGE_VARIATIONS: ClassVar[bool] = False
    SUPPORTS_AUDIO_TRANSCRIPTIONS: ClassVar[bool] = False
    SUPPORTS_AUDIO_TRANSLATIONS: ClassVar[bool] = False
    SUPPORTS_AUDIO_SPEECH: ClassVar[bool] = False
    SUPPORTS_VISION: ClassVar[bool] = False
    SUPPORTS_INPUT_AUDIO: ClassVar[bool] = False
    SUPPORTS_TOOL_CALLING: ClassVar[bool] = False
    SUPPORTS_PARALLEL_TOOL_CALLS: ClassVar[bool] = False
    SUPPORTS_STRUCTURED_OUTPUT: ClassVar[bool] = False
    SUPPORTS_JSON_SCHEMA: ClassVar[bool] = False
    SUPPORTS_RESPONSES_RETRIEVE: ClassVar[bool] = False
    SUPPORTS_RESPONSES_DELETE: ClassVar[bool] = False
    SUPPORTS_RESPONSES_CANCEL: ClassVar[bool] = False
    SUPPORTS_RESPONSES_INPUT_ITEMS: ClassVar[bool] = False
    SUPPORTS_RESPONSES_INPUT_TOKENS: ClassVar[bool] = False
    SUPPORTS_MODEL_VARIANT_DISCOVERY: ClassVar[bool] = False
    SUPPORTS_CLONING: ClassVar[bool] = False
    CLONABLE_FIELDS: ClassVar[tuple[ClonableFieldProtocol, ...]] = ()
    SUPPORTED_MODALITIES: ClassVar[Sequence[str]] = (OpenAIModality.TEXT.value,)
    EXTERNAL_PROVIDER_MODE: ClassVar[Enum] = ExternalProviderMode.NONE
    OPENAI_FEATURE_MATRIX: ClassVar[tuple[tuple[str, tuple[tuple[str, str], ...]], ...]] = (
        OPENAI_FEATURE_MATRIX
    )
    soai_version = property(lambda _self: __version__)

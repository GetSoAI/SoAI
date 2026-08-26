"""SoAI - Plugin instance and runtime type protocols [backend/core/plugins/protocols_instance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterable, Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict

from core.openai.compatibility import ExternalProviderMode
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ClonableFieldProtocol",
    "FilesProtocol",
    "ModelContextProtocol",
    "PluginActionResponseProtocol",
    "PluginInstanceProtocol",
    "PluginSurfaceMetadataProtocol",
    "PluginStagedUploadProtocol",
    "RemoteModelSearchResultProtocol",
    "RemoteModelSearchVariantProtocol",
)


class PluginActionResponseProtocol(Protocol):
    success: bool
    status_code: int
    payload: JSONDict | None
    error_type: str | None
    error_message: str | None
    extra: JSONDict | None


class PluginStagedUploadProtocol(Protocol):
    original_filename: str
    temp_path: str
    size_bytes: int


class FilesProtocol(Protocol):
    def resolve_path(self, path: str | os.PathLike[str]) -> str: ...


class ModelContextProtocol(Protocol):
    universal_id: str
    source_model_id: str
    plugin: str
    model_path: str | None
    parameters: JSONDict
    provider_details: JSONDict | None


class RemoteModelSearchVariantProtocol(Protocol): ...


class RemoteModelSearchResultProtocol(Protocol): ...


class ClonableFieldProtocol(TypedDict):
    name: str
    display_name: str
    field_type: Literal["port", "path", "string"]
    required: bool


class PluginSurfaceMetadataProtocol(Protocol):
    NAME: str
    AUTHOR_SOAIPLUGIN: str
    DESCRIPTION_SOAIPLUGIN: str
    WEBSITE_SOAIPLUGIN: str
    VERSION_SOAIPLUGIN: str
    LICENSE_SOAIPLUGIN: str
    REQUIRED_SOAI_VERSION: str
    MODEL_REPOSITORY: str | None
    MODEL_TYPES: tuple[str, ...]
    WEBSITE_BACKEND: str | None
    LICENSE_MANAGED_BACKEND: str | None
    MAX_CONCURRENT_REQUESTS: int | None
    REQUIRED_SYSTEM_CAPABILITIES: Mapping[str, JSONValue]
    DEFAULT_CONFIGURATION: Mapping[str, JSONValue]
    ALIASES: tuple[str, ...]
    PLUGIN_DEPENDENCIES: tuple[str, ...]
    PACKAGE_DEPENDENCIES: tuple[str, ...]
    LOCAL_RESOURCES: bool
    LOCAL_MODELS: bool
    PERSISTENT: bool
    SUPPORTS_BACKEND_INSTALLATION: bool
    SUPPORTS_BACKEND_PROCESS_TRACKING: bool
    SUPPORTS_CONFIGURATION: bool
    SUPPORTS_GPU_BINDING: bool
    SUPPORTS_PROMPT_TOKEN_COUNTING: bool
    SUPPORTS_MODEL_VARIANT_DISCOVERY: bool
    SUPPORTS_MODEL_DOWNLOAD: bool
    SUPPORTS_MODEL_DELETION: bool
    SUPPORTS_MODEL_SEARCH: bool
    SUPPORTS_CLONING: bool
    SUPPORTS_EXTERNAL_PROVIDERS: bool
    EXTERNAL_PROVIDER_MODE: ExternalProviderMode
    EXTERNAL_PROVIDER_DEFAULTS: Mapping[str, JSONValue]
    BACKEND_VARIANT_OPTIONS: Sequence[JSONDict]
    SUPPORTED_MODALITIES: Sequence[str]
    CLONABLE_FIELDS: tuple[ClonableFieldProtocol, ...]
    WELCOME_MESSAGE: str | None


class PluginInstanceProtocol(PluginSurfaceMetadataProtocol, Protocol):
    plugin_name: str
    install_path: str | None
    openai_capabilities: JSONDict

    def get_models_directory(self) -> str: ...

    async def get_default_configuration(self) -> JSONDict: ...

    async def refresh_runtime_configuration(self) -> JSONDict: ...

    async def check_system_dependencies(self) -> tuple[bool, str]: ...

    async def install_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        backend_variant_id: str,
    ) -> bool: ...

    async def update_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        backend_variant_id: str,
    ) -> bool: ...

    async def remove_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        delete_models: bool,
    ) -> bool: ...

    def get_log_file_path(self) -> str | None: ...

    async def discover_models(
        self,
        existing_models: dict[str, JSONDict] | None = None,
    ) -> dict[str, JSONDict] | None: ...

    async def get_status(self) -> JSONDict: ...

    async def get_parameter_schema(self) -> JSONDict: ...

    async def get_available_variants(self, model_id: str) -> list[JSONDict]: ...

    async def get_backend_process_pids(self) -> list[int]: ...

    async def health_ping(self) -> tuple[bool, str]: ...

    def start(self) -> bool | Awaitable[bool]: ...

    async def start_with_model(
        self,
        model_context: ModelContextProtocol,
        context: RequestContext,
    ) -> bool: ...

    async def stop(self) -> bool: ...

    async def cancel_task(self, task_id: str, context: RequestContext) -> tuple[bool, str]: ...

    async def cleanup_partial_installation(self) -> None: ...

    async def download_model(
        self,
        model_id: str,
        quantization: str | None,
        output_callback: Callable[[JSONDict], Awaitable[None]],
        shutdown_event: asyncio.Event,
    ) -> tuple[bool, str] | tuple[bool, str, JSONDict | None]: ...

    async def get_model_download_plan(
        self,
        model_id: str,
        quantization: str | None,
    ) -> JSONDict: ...

    async def handle_request(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContextProtocol,
    ) -> JSONDict | AsyncIterable[bytes]: ...

    async def count_prompt_tokens(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContextProtocol,
    ) -> JSONDict: ...

    async def handle_embedding_request(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContextProtocol,
    ) -> JSONDict: ...

    async def check_for_backend_update(self) -> JSONDict: ...

    async def search_remote_models(
        self,
        query: str,
        limit: int = 10,
    ) -> Sequence[RemoteModelSearchResultProtocol]: ...

    async def delete_model(
        self,
        model_info: JSONDict,
        output_callback: Callable[[JSONDict], Awaitable[None]],
        shutdown_event: asyncio.Event,
    ) -> tuple[bool, str]: ...

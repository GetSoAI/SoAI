"""SoAI - Plugin SDK typing-only stubs for public exports [backend/plugin_sdk/public_exports_type_stubs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import ClassVar, override

from core.config.protocols import ConfigProtocol
from core.events.protocols import EventBusProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.models.remote_model_search_types import RemoteModelSearchResult
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_instance import FilesProtocol
from core.plugins.protocols_runtime import (
    PluginHardwareRuntimeProtocol,
    PluginModelRegistryRuntimeProtocol,
    PluginRuntimeFailureReporterProtocol,
    PluginStorageRuntimeProtocol,
)
from core.plugins.runtime_services import PluginRuntimeServices
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict
from core.types.protocols import HttpClientProtocol
from plugin_sdk.runtime import ModelContext

__all__ = (
    "BasePlugin",
    "enforce_offline_policy",
    "require_online_mode",
    "validate_runtime_host_port",
)


async def enforce_offline_policy(
    flags: RuntimeFlagsViewProtocol,
    target_url: str,
    *,
    source: str,
) -> None:
    del flags, target_url, source


def require_online_mode(flags: RuntimeFlagsViewProtocol, *, source: str) -> None:
    del flags, source


async def validate_runtime_host_port(
    flags: RuntimeFlagsViewProtocol,
    *,
    host: str,
    port: int,
    source: str,
    scheme: str = "https",
) -> str | None:
    del flags, host, port, source, scheme
    return None


class _NullAsyncContextManager(AbstractAsyncContextManager[None]):
    @override
    async def __aenter__(self) -> None:
        return None

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        del exc_type, exc, tb
        return None


class BasePlugin:
    plugin_name: str
    config: ConfigProtocol
    event_bus: EventBusProtocol
    metrics: MetricsManagerProtocol
    model_registry: PluginModelRegistryRuntimeProtocol
    plugin_manager: PluginManagerProtocol
    runtime_reporter: PluginRuntimeFailureReporterProtocol
    hw_manager: PluginHardwareRuntimeProtocol | None
    storage_manager: PluginStorageRuntimeProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    files: FilesProtocol
    plugin_config: JSONDict
    http_client: HttpClientProtocol
    install_path: str
    temp_directory: str
    openai_capabilities: JSONDict
    AUTHOR_SOAIPLUGIN: ClassVar[str]
    DESCRIPTION_SOAIPLUGIN: ClassVar[str]
    EXTERNAL_PROVIDER_DEFAULTS: ClassVar[JSONDict]
    BACKEND_VARIANT_OPTIONS: ClassVar[list[JSONDict]]
    LICENSE_SOAIPLUGIN: ClassVar[str]
    LICENSE_MANAGED_BACKEND: ClassVar[str | None]
    SUPPORTS_MODEL_DELETION: ClassVar[bool]
    SUPPORTS_PROMPT_TOKEN_COUNTING: ClassVar[bool]
    VERSION_SOAIPLUGIN: ClassVar[str]

    def __init__(
        self,
        plugin_name: str,
        *,
        config: ConfigProtocol,
        event_bus: EventBusProtocol,
        runtime: PluginRuntimeServices,
    ) -> None:
        del self, plugin_name, config, event_bus, runtime

    def get_models_directory(self) -> str:
        return ""

    async def refresh_runtime_configuration(self) -> JSONDict:
        return {}

    async def apply_runtime_configuration(self, config_data: JSONDict) -> JSONDict:
        return config_data

    async def get_available_variants(self, model_id: str) -> list[JSONDict]:
        del self, model_id
        return []

    async def get_model_download_plan(
        self,
        model_id: str,
        quantization: str | None,
    ) -> JSONDict:
        del self, model_id, quantization
        return {}

    async def search_remote_models(
        self,
        query: str,
        limit: int = 10,
    ) -> Sequence[RemoteModelSearchResult | JSONDict]:
        del self, query, limit
        return []

    def supports_modality(self, modality: str) -> bool:
        del modality
        return False

    def get_default_log_path(self) -> str:
        return ""

    @classmethod
    def get_openai_capabilities(cls) -> JSONDict:
        del cls
        return {}

    @classmethod
    def get_default_configuration_template(
        cls,
        config: ConfigProtocol | None = None,
        files: FilesProtocol | None = None,
        plugin_name: str | None = None,
    ) -> JSONDict:
        del cls, config, files, plugin_name
        return {}

    async def calculate_model_hash(
        self,
        *,
        model_path: str,
        existing_model_info: JSONDict | None = None,
    ) -> str | None:
        del self, model_path, existing_model_info
        return None

    async def calculate_model_hash_and_metadata(
        self,
        *,
        model_path: str,
        existing_model_info: JSONDict | None = None,
    ) -> tuple[str | None, float | None, float | None]:
        del self, model_path, existing_model_info
        return None, None, None

    async def open_log_file(self, command: Sequence[str] | None = None) -> io.BufferedIOBase:
        del self, command
        return io.BytesIO()

    async def handle_embedding_request(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContext,
    ) -> JSONDict:
        del self, request_json, context, model_context
        return {}

    async def count_prompt_tokens(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContext,
    ) -> JSONDict:
        del self, request_json, context, model_context
        return {
            "precision": "unsupported",
            "prompt_tokens": None,
            "source": "plugin",
            "reason": "Prompt token counting is not implemented by the typing stub.",
            "tokenizer_id": None,
        }

    async def enforce_offline_policy(self, target_url: str, *, source: str) -> None:
        del self, target_url, source

    def require_online_mode(self, *, source: str) -> None:
        del self, source

    def track_request(
        self,
        *,
        count_total: bool = True,
        record_timing: bool = True,
        record_success: bool = True,
    ) -> AbstractAsyncContextManager[None]:
        del self, count_total, record_timing, record_success
        return _NullAsyncContextManager()

"""SoAI - Core base plugin abstract interface and contract [backend/core/plugins/base_plugin.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import abc
import asyncio
import io
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, override

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import StateError
from core.plugins.base_plugin_capabilities import build_openai_capabilities
from core.plugins.base_plugin_defaults import BasePluginDefaults
from core.plugins.base_plugin_surface import (
    get_default_configuration_template,
    get_default_log_path,
    get_models_directory,
    open_log_file_for_command,
    supports_modality,
)
from core.plugins.protocols_instance import ModelContextProtocol
from core.plugins.protocols_runtime import PluginEventBusRuntimeProtocol
from core.plugins.runtime_services import PluginRuntimeServices
from core.plugins.runtime_support import (
    calculate_model_hash,
    calculate_model_hash_and_metadata,
    initialize_temp_directory,
    track_request,
)
from core.runtime.network_policy import enforce_offline_policy, require_online_mode
from core.runtime.request_context import RequestContext

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("BasePlugin",)


class BasePlugin(BasePluginDefaults, abc.ABC):
    def __init__(
        self,
        plugin_name: str,
        *,
        config: ConfigProtocol,
        event_bus: PluginEventBusRuntimeProtocol,
        runtime: PluginRuntimeServices,
    ) -> None:
        self.plugin_name = plugin_name
        self.config = config
        self.event_bus = event_bus
        self.metrics = runtime.metrics_manager
        self.model_registry = runtime.model_registry
        self.plugin_manager = runtime.plugin_manager
        self.runtime_reporter = runtime.runtime_reporter
        self.hw_manager = runtime.hw_manager
        self.storage_manager = runtime.storage_manager
        self.runtime_flags = runtime.runtime_flags
        self.files = runtime.files
        if self.files is None:
            raise StateError("Plugin runtime must provide a Files-compatible helper.")
        self.plugin_config: Mapping[str, JSONValue] = runtime.plugin_config
        self.http_client = runtime.http_client
        self.install_path = runtime.install_path
        if self.runtime_flags is None:
            raise StateError(
                "Plugin runtime must provide a RuntimeFlagsViewProtocol-compatible helper.",
            )
        self.temp_directory = initialize_temp_directory(config)

    get_models_directory = get_models_directory
    supports_modality = supports_modality
    get_default_log_path = get_default_log_path
    get_default_configuration_template = classmethod(get_default_configuration_template)

    async def refresh_runtime_configuration(self) -> JSONDict:
        latest_config = await self.plugin_manager.get_plugin_configuration(self.plugin_name)
        return await self.apply_runtime_configuration(dict(latest_config))

    async def apply_runtime_configuration(self, config_data: JSONDict) -> JSONDict:
        refreshed_config = dict(config_data)
        self.plugin_config = refreshed_config
        return refreshed_config

    async def calculate_model_hash(
        self,
        *,
        model_path: str,
        existing_model_info: JSONDict | None = None,
    ) -> str | None:
        return await calculate_model_hash(
            model_path=model_path,
            existing_model_info=existing_model_info,
            plugin_name=self.plugin_name,
        )

    async def calculate_model_hash_and_metadata(
        self,
        *,
        model_path: str,
        existing_model_info: JSONDict | None = None,
    ) -> tuple[str | None, float | None, float | None]:
        return await calculate_model_hash_and_metadata(
            model_path=model_path,
            existing_model_info=existing_model_info,
            plugin_name=self.plugin_name,
        )

    async def open_log_file(self, command: Sequence[str] | None = None) -> io.BufferedIOBase:
        return await open_log_file_for_command(self, command)

    @abc.abstractmethod
    async def get_parameter_schema(self) -> JSONDict: ...

    @abc.abstractmethod
    async def get_default_configuration(self) -> JSONDict: ...

    @abc.abstractmethod
    async def check_system_dependencies(self) -> tuple[bool, str]: ...

    @abc.abstractmethod
    async def install_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        backend_variant_id: str,
    ) -> bool: ...

    @abc.abstractmethod
    async def update_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        backend_variant_id: str,
    ) -> bool: ...

    @abc.abstractmethod
    async def remove_backend(
        self,
        output_callback: Callable[[str], Awaitable[None] | None],
        delete_models: bool,
    ) -> bool: ...

    async def cleanup_partial_installation(self) -> None:
        return None

    @abc.abstractmethod
    async def get_status(self) -> JSONDict: ...

    @abc.abstractmethod
    async def check_for_backend_update(self) -> JSONDict: ...

    @abc.abstractmethod
    async def health_ping(self) -> tuple[bool, str]: ...

    @abc.abstractmethod
    def get_log_file_path(self) -> str | None: ...

    @abc.abstractmethod
    async def discover_models(
        self,
        existing_models: dict[str, JSONDict] | None = None,
    ) -> dict[str, JSONDict] | None: ...

    @abc.abstractmethod
    async def start(self) -> bool: ...

    @abc.abstractmethod
    async def start_with_model(
        self,
        model_context: ModelContextProtocol,
        context: RequestContext,
    ) -> bool: ...

    @abc.abstractmethod
    async def stop(self) -> bool: ...

    async def get_backend_process_pids(self) -> list[int]:
        return []

    @abc.abstractmethod
    async def cancel_task(self, task_id: str, context: RequestContext) -> tuple[bool, str]: ...

    @abc.abstractmethod
    async def load_model_in_service(
        self,
        model_context: ModelContextProtocol,
        context: RequestContext,
    ) -> bool: ...

    @abc.abstractmethod
    async def unload_model_in_service(self, universal_id: str) -> bool: ...

    @abc.abstractmethod
    async def get_model_download_plan(
        self,
        model_id: str,
        quantization: str | None,
    ) -> JSONDict: ...

    @abc.abstractmethod
    async def download_model(
        self,
        model_id: str,
        quantization: str | None,
        output_callback: Callable[[JSONDict], Awaitable[None]],
        shutdown_event: asyncio.Event,
    ) -> tuple[bool, str] | tuple[bool, str, JSONDict | None]: ...

    @abc.abstractmethod
    async def delete_model(
        self,
        model_info: JSONDict,
        output_callback: Callable[[JSONDict], Awaitable[None]],
        shutdown_event: asyncio.Event,
    ) -> tuple[bool, str]: ...

    @abc.abstractmethod
    async def handle_request(
        self,
        request_json: JSONDict,
        context: RequestContext,
        model_context: ModelContextProtocol,
    ) -> JSONDict | AsyncGenerator[bytes]: ...

    @asynccontextmanager
    async def track_request(
        self,
        *,
        count_total: bool = True,
        record_timing: bool = True,
        record_success: bool = True,
    ) -> AsyncGenerator[None]:
        async with track_request(
            metrics=self.metrics,
            plugin_name=self.plugin_name,
            count_total=count_total,
            record_timing=record_timing,
            record_success=record_success,
        ):
            yield

    @classmethod
    @override
    def get_openai_capabilities(cls) -> JSONDict:
        return build_openai_capabilities(cls)

    async def enforce_offline_policy(self, target_url: str, *, source: str) -> None:
        await enforce_offline_policy(self.runtime_flags, target_url, source=source)

    def require_online_mode(self, *, source: str) -> None:
        require_online_mode(self.runtime_flags, source=source)

"""SoAI - Plugin runtime protocol surface [backend/core/plugins/protocols_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import TYPE_CHECKING, ClassVar, Protocol

from core.config.protocols import ConfigProtocol
from core.logging.protocols import LoggerProtocol
from core.metrics.protocols import MetricsRecorderProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.plugins.protocols_instance import FilesProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "BasePluginCapabilitySurfaceProtocol",
    "DefaultConfigurationProviderProtocol",
    "LoggerProtocol",
    "PluginEventBusRuntimeProtocol",
    "PluginHardwareRuntimeProtocol",
    "PluginManagerRuntimeServiceProtocol",
    "PluginMetricsRuntimeProtocol",
    "PluginModelRegistryRuntimeProtocol",
    "PluginRuntimeFailureReporterProtocol",
    "PluginRuntimeFlagsProtocol",
    "PluginStorageReservationLeaseProtocol",
    "PluginStorageRuntimeProtocol",
    "PluginStorageWriteClaimProtocol",
    "PluginSurfaceProtocol",
)


class PluginSurfaceProtocol(Protocol):
    plugin_config: Mapping[str, JSONValue]
    files: FilesProtocol
    config: ConfigProtocol
    plugin_name: str
    SUPPORTED_MODALITIES: ClassVar[Sequence[str]]


class BasePluginCapabilitySurfaceProtocol(PluginSurfaceProtocol, Protocol):
    SUPPORTS_EMBEDDINGS: ClassVar[bool]
    SUPPORTS_MODEL_VARIANT_DISCOVERY: ClassVar[bool]
    SUPPORTS_MODEL_SEARCH: ClassVar[bool]
    SUPPORTS_PROMPT_TOKEN_COUNTING: ClassVar[bool]


class DefaultConfigurationProviderProtocol(Protocol):
    DEFAULT_CONFIGURATION: ClassVar[Mapping[str, JSONValue]]


class PluginMetricsRuntimeProtocol(MetricsRecorderProtocol, Protocol): ...


class PluginModelRegistryRuntimeProtocol(Protocol):
    async def model_get_info(self, universal_id: str) -> JSONDict | None: ...

    async def get_external_provider_for_model(self, universal_id: str) -> JSONDict | None: ...

    async def provider_get_external(
        self,
        provider_id: str,
        decrypt_key: bool = False,
    ) -> JSONDict | None: ...

    async def provider_list_for_plugin(self, plugin_name: str) -> list[JSONDict]: ...

    async def update_provider_status(
        self,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None: ...

    async def upsert_plugin_managed_provider(
        self,
        plugin_name: str,
        provider_id: str,
        name: str,
        url: str,
    ) -> JSONDict | None: ...


class PluginManagerRuntimeServiceProtocol(Protocol):
    async def get_plugin_configuration(self, plugin_name: str) -> JSONDict: ...

    async def set_plugin_configuration(self, plugin_name: str, config_data: JSONDict) -> bool: ...


class PluginRuntimeFailureReporterProtocol(Protocol):
    async def report_runtime_failure(
        self,
        *,
        component: str,
        failure_code: str,
        exit_status: int | None = None,
    ) -> None: ...


class PluginHardwareRuntimeProtocol(Protocol):
    async def get_system_capabilities(self) -> JSONDict: ...

    async def get_system_info(
        self,
        components: list[str] | None = None,
        cache: bool = True,
        include_gpu_capabilities: bool = True,
    ) -> JSONDict: ...


class PluginRuntimeFlagsProtocol(RuntimeFlagsViewProtocol, Protocol): ...


class PluginStorageReservationLeaseProtocol(Protocol):
    async def claim_write_bytes(self, bytes_to_write: int) -> PluginStorageWriteClaimProtocol: ...
    async def release(self) -> None: ...
    async def __aenter__(self) -> PluginStorageReservationLeaseProtocol: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class PluginStorageWriteClaimProtocol(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def __aenter__(self) -> PluginStorageWriteClaimProtocol: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class PluginStorageRuntimeProtocol(Protocol):
    async def reserve_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> PluginStorageReservationLeaseProtocol: ...


class PluginEventBusRuntimeProtocol(Protocol):
    async def publish(self, event: Event) -> None: ...

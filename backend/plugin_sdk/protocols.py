"""SoAI - Plugin SDK protocol surface [backend/plugin_sdk/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Protocol

from core.plugins.protocols_runtime import (
    BasePluginCapabilitySurfaceProtocol,
    DefaultConfigurationProviderProtocol,
    LoggerProtocol,
    PluginEventBusRuntimeProtocol,
    PluginHardwareRuntimeProtocol,
    PluginManagerRuntimeServiceProtocol,
    PluginMetricsRuntimeProtocol,
    PluginModelRegistryRuntimeProtocol,
    PluginRuntimeFailureReporterProtocol,
    PluginRuntimeFlagsProtocol,
    PluginStorageReservationLeaseProtocol,
    PluginStorageRuntimeProtocol,
    PluginStorageWriteClaimProtocol,
    PluginSurfaceProtocol,
)
from core.types.json import JSONValue

__all__ = (
    "BasePluginCapabilitySurfaceProtocol",
    "AcceleratorInventoryProviderProtocol",
    "ReservedWriteDiskReservationLeaseProtocol",
    "LoggerProtocol",
    "DefaultConfigurationProviderProtocol",
    "ReservedWriteDiskWriteClaimProtocol",
    "PluginEventBusRuntimeProtocol",
    "LazyPluginSdkExportProtocol",
    "PluginManagerRuntimeServiceProtocol",
    "PluginHardwareRuntimeProtocol",
    "ReservedWriteDiskReservationProviderProtocol",
    "PluginModelRegistryRuntimeProtocol",
    "PluginMetricsRuntimeProtocol",
    "PluginRuntimeFlagsProtocol",
    "PluginRuntimeFailureReporterProtocol",
    "PluginStorageRuntimeProtocol",
    "PluginStorageReservationLeaseProtocol",
    "PluginSurfaceProtocol",
    "PluginStorageWriteClaimProtocol",
)


class LazyPluginSdkExportProtocol(Protocol): ...


class AcceleratorInventoryProviderProtocol(Protocol):
    async def get_system_info(self, components: list[str], cache: bool) -> JSONValue: ...


class ReservedWriteDiskWriteClaimProtocol(Protocol):
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def __aenter__(self) -> ReservedWriteDiskWriteClaimProtocol: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class ReservedWriteDiskReservationLeaseProtocol(Protocol):
    async def claim_write_bytes(
        self,
        bytes_to_write: int,
    ) -> ReservedWriteDiskWriteClaimProtocol: ...
    async def release(self) -> None: ...
    async def __aenter__(self) -> ReservedWriteDiskReservationLeaseProtocol: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class ReservedWriteDiskReservationProviderProtocol(Protocol):
    async def reserve_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> ReservedWriteDiskReservationLeaseProtocol: ...

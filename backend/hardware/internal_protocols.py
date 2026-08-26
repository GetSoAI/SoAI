"""SoAI - Hardware subsystem internal protocols [backend/hardware/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Protocol

from core.logging.protocols import TraceLogger

if TYPE_CHECKING:
    from core.hardware.protocols import DatabaseHardwareProtocol
    from core.types.json import JSONDict
    from hardware.manager.manager_state import HardwareManagerState

__all__ = (
    "DiskSpeedDatabaseProtocol",
    "DiskSpeedManagerProtocol",
    "GPUInfoCacheServiceProtocol",
    "GPUVendorDetectionServiceProtocol",
    "GpuCapabilitiesServiceProtocol",
    "MinimumSpecsManagerProtocol",
    "MonitoringCoordinatorProtocol",
    "MonitoringManagerProtocol",
    "NetworkSpeedDatabaseProtocol",
    "NetworkSpeedManagerProtocol",
    "SystemInfoSnapshotManagerProtocol",
)


class GPUInfoCacheServiceProtocol(Protocol):
    def get_cached(self, cache_key: bool, now: float) -> JSONDict | None: ...

    def get_cached_with_gpus(self, now: float) -> JSONDict | None: ...

    def set_cached(self, cache_key: bool, now: float, payload: JSONDict) -> None: ...

    def invalidate_cache(self) -> None: ...

    def revision(self) -> int: ...

    def set_cache_ttl(self, cache_ttl_seconds: float) -> None: ...


class GPUVendorDetectionServiceProtocol(Protocol):
    def get_system_gpu_vendors(self) -> set[str]: ...

    def invalidate_cache(self) -> None: ...

    def set_cache_ttl(self, cache_ttl_seconds: float) -> None: ...


class GpuCapabilitiesServiceProtocol(Protocol):
    async def get_cached_capabilities(self) -> JSONDict | None: ...

    async def get_capabilities(self, enrich_fn: Callable[[JSONDict], JSONDict]) -> JSONDict: ...


class DiskSpeedDatabaseProtocol(Protocol):
    def get_latest_speed_test_snapshot(
        self,
    ) -> Coroutine[None, None, JSONDict | None]: ...


class DiskSpeedManagerProtocol(Protocol):
    @property
    def database_hardware(self) -> DatabaseHardwareProtocol | None: ...

    @property
    def main_loop(self) -> asyncio.AbstractEventLoop | None: ...

    @property
    def logger(self) -> TraceLogger: ...

    @property
    def state(self) -> HardwareManagerState: ...

    @property
    def disk_speed_cache_timestamp(self) -> float: ...

    @property
    def cached_disk_speed(self) -> JSONDict | None: ...

    def set_disk_speed_cache(self, snapshot: JSONDict | None, *, cached_at: float) -> None: ...


class MinimumSpecsManagerProtocol(Protocol):
    @property
    def min_specs_enabled(self) -> bool: ...

    @property
    def logger(self) -> TraceLogger: ...

    @property
    def base_dir(self) -> str: ...


class MonitoringCoordinatorProtocol(Protocol):
    def dispatch_snapshot(self, info: JSONDict, loop: asyncio.AbstractEventLoop | None) -> None: ...


class MonitoringManagerProtocol(Protocol):
    @property
    def monitoring_interval_ms(self) -> int: ...

    @property
    def main_loop(self) -> asyncio.AbstractEventLoop | None: ...

    @property
    def logger(self) -> TraceLogger: ...

    @property
    def monitoring_stop_event(self) -> threading.Event: ...

    def sync_get_system_info(
        self,
        *,
        cache: bool,
        include_gpu_capabilities: bool = True,
    ) -> JSONDict: ...

    @property
    def monitoring_coordinator(self) -> MonitoringCoordinatorProtocol: ...


class NetworkSpeedDatabaseProtocol(Protocol):
    def get_latest_network_speed_snapshot(
        self,
    ) -> Coroutine[None, None, JSONDict]: ...


class NetworkSpeedManagerProtocol(Protocol):
    @property
    def last_network_stats(self) -> dict[str, JSONDict]: ...

    @property
    def database_hardware(self) -> DatabaseHardwareProtocol | None: ...

    @property
    def main_loop(self) -> asyncio.AbstractEventLoop | None: ...

    @property
    def logger(self) -> TraceLogger: ...

    @property
    def network_speed_cache_ttl_seconds(self) -> float: ...

    @property
    def cached_network_speed(self) -> JSONDict: ...

    @property
    def network_speed_cache_timestamp(self) -> float: ...

    @property
    def loaded_network_speed_from_db(self) -> bool: ...

    def set_network_speed_cache(
        self,
        snapshot: JSONDict,
        *,
        cached_at: float,
        loaded_from_db: bool,
    ) -> None: ...


class SystemInfoSnapshotManagerProtocol(
    DiskSpeedManagerProtocol,
    NetworkSpeedManagerProtocol,
    Protocol,
): ...

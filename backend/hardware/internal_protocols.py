"""SoAI - Hardware subsystem internal protocols [backend/hardware/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from core.logging.protocols import TraceLogger

if TYPE_CHECKING:
    from concurrent.futures import Executor

    from core.concurrency.deadlines import MonotonicDeadline
    from core.errors.exceptions import SoAIError
    from core.hardware.protocols import DatabaseHardwareProtocol
    from core.types.json import JSONDict
    from hardware.manager.manager_state import HardwareManagerState

__all__ = (
    "DiskSpeedManagerProtocol",
    "GPUInfoCacheServiceProtocol",
    "GPUInfoObservation",
    "GPUProbeExecutorFactoryProtocol",
    "GPUVendorDetectionServiceProtocol",
    "GpuCapabilitiesServiceProtocol",
    "MinimumSpecsManagerProtocol",
    "MonitoringCoordinatorProtocol",
    "MonitoringManagerProtocol",
    "NetworkSpeedManagerProtocol",
    "SystemInfoSnapshotManagerProtocol",
)


@dataclass(frozen=True, slots=True)
class GPUInfoObservation:
    payload: JSONDict
    observed_at_ms: int | None
    sampled_current: bool
    refresh_failed: bool
    inventory_revision: int | None = None
    valid_until_ms: int | None = None
    diagnostics: tuple[SoAIError, ...] = ()
    coverage_complete: bool = True
    refresh_error: SoAIError | None = None


class GPUProbeExecutorFactoryProtocol(Protocol):
    def __call__(self) -> Executor: ...


class GPUInfoCacheServiceProtocol(Protocol):
    def acquire_observation(
        self,
        cache_key: bool,
        acquisition: Callable[[int, int], GPUInfoObservation],
        *,
        monotonic_clock_ms: Callable[[], float],
        deadline: MonotonicDeadline | None = None,
    ) -> GPUInfoObservation: ...

    @property
    def lock(self) -> threading.RLock: ...

    def get_cached(self, cache_key: bool, now: float) -> JSONDict | None: ...

    def get_cached_with_gpus(self, now: float) -> JSONDict | None: ...

    def get_cached_observation(self, cache_key: bool, now: float) -> GPUInfoObservation | None: ...

    def get_retained_observation(self) -> GPUInfoObservation | None: ...

    def get_retained_observations(self) -> tuple[GPUInfoObservation, ...]: ...

    def begin_acquisition(self, cache_key: bool) -> int: ...

    def is_current_acquisition(self, cache_key: bool, sequence: int) -> bool: ...

    def set_cached(self, cache_key: bool, now: float, payload: JSONDict) -> None: ...

    def publish_acquisition(
        self, cache_key: bool, now: float, payload: JSONDict, *, revision: int, sequence: int
    ) -> GPUInfoObservation: ...

    def invalidate_cache(self, *, owner: str, reason: str) -> None: ...

    def shutdown(self) -> None: ...

    def start(self) -> None: ...

    def observation_diagnostics(self) -> JSONDict: ...

    def request_refresh(self) -> None: ...

    def revision(self) -> int: ...

    def set_cache_ttl(self, cache_ttl_seconds: float) -> None: ...


class GPUVendorDetectionServiceProtocol(Protocol):
    def get_system_gpu_vendors(self) -> set[str]: ...

    def invalidate_cache(self) -> None: ...

    def set_cache_ttl(self, cache_ttl_seconds: float) -> None: ...


class GpuCapabilitiesServiceProtocol(Protocol):
    async def get_cached_capabilities(self) -> JSONDict | None: ...

    async def get_capabilities(self, enrich_fn: Callable[[JSONDict], JSONDict]) -> JSONDict: ...


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


class NetworkSpeedManagerProtocol(Protocol):
    @property
    def state(self) -> HardwareManagerState: ...

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
):
    def get_network_info(self) -> JSONDict: ...

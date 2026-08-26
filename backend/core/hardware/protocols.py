"""SoAI - Hardware subsystem protocol definitions [backend/core/hardware/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Protocol

from core.database.protocols import DatabaseCoreProtocol
from core.hardware.protocols_soaibench import DatabaseSoAIBenchProtocol
from core.hardware.types import GPUSettingsOutcome
from core.logging.protocols import LoggerProtocol, TraceLogger
from core.runtime.protocols import RuntimePlatformViewProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from core.types.protocols import HttpClientProtocol

__all__ = ()


class HardwareManagerProtocol(Protocol):
    @property
    def enabled(self) -> bool: ...
    @property
    def logger(self) -> TraceLogger: ...
    @property
    def history_config(self) -> Mapping[str, JSONValue]: ...
    @property
    def nvidia_nvml_gate(self) -> NvmlGateProtocol: ...
    def get_network_info(self) -> JSONDict: ...
    async def get_system_capabilities(self) -> JSONDict: ...
    async def get_system_info(
        self,
        components: Sequence[str] | None = None,
        cache: bool = True,
        include_gpu_capabilities: bool = True,
    ) -> JSONDict: ...
    async def get_gpu_capabilities(self) -> JSONDict: ...
    async def get_historical_data(
        self,
        *,
        start_ts_ms: int,
        end_ts_ms: int,
        points: int,
        interval_ms: int,
        aggregation: str,
        component: str = "cpu",
        gpu_index: int | None = None,
        identifier: str | None = None,
    ) -> JSONDict: ...
    async def build_variant_support_context(
        self,
        models_dir: str | None,
        include_speed_tests: bool,
        *,
        database_hardware: DatabaseHardwareProtocol | None = None,
        http_client: HttpClientProtocol | None = None,
    ) -> VariantSupportContextProtocol: ...
    async def start_monitoring(self) -> bool: ...
    async def shutdown(self) -> None: ...


class VariantSupportContextProtocol(Protocol):
    disk_free_bytes: int | None
    disk_speed_template: JSONDict | None
    network_speed_template: JSONDict | None
    available_vram_gb: float | None
    total_memory_gb: float | None
    system_ram_gb: float | None


class HardwareGpuTuningProtocol(Protocol):
    logger: TraceLogger

    @property
    def gpu_operation_lock(self) -> asyncio.Lock: ...

    def set_main_loop(self, loop: asyncio.AbstractEventLoop) -> None: ...
    def enrich_gpu_capabilities(self, capabilities: JSONDict) -> JSONDict: ...
    async def get_gpu_capabilities(self) -> JSONDict: ...
    async def process_gpu_settings_request(
        self,
        payload: Mapping[str, JSONValue],
    ) -> GPUSettingsOutcome: ...
    async def list_gpu_slots(self, device_id: str | None = None) -> JSONDict: ...
    async def preview_gpu_slot(self, device_id: str, slot: str | int) -> JSONDict: ...
    async def store_gpu_slot(
        self,
        device_id: str,
        slot: str | int,
        settings: Mapping[str, JSONValue],
        field_modes: Mapping[str, JSONValue] | None = None,
        apply_at_boot: bool | None = None,
    ) -> JSONDict: ...
    async def toggle_gpu_slot_boot(
        self,
        device_id: str,
        slot: str | int,
        enabled: bool,
    ) -> JSONDict: ...
    async def clear_gpu_slot(self, device_id: str, slot: str | int) -> JSONDict: ...
    async def apply_gpu_slot(
        self,
        device_id: str,
        slot: str | int,
        apply_at_boot: bool | None = None,
    ) -> JSONDict: ...
    async def apply_gpu_settings_direct(self, device_id: str, settings: JSONDict) -> JSONDict: ...
    async def apply_gpu_settings_direct_unlocked(
        self,
        device_id: str,
        settings: JSONDict,
    ) -> JSONDict: ...
    def invalidate_gpu_caches(self) -> None: ...
    async def apply_startup_gpu_settings(self) -> None: ...
    async def clear_dirty_shutdown_flag(self) -> None: ...


class HardwareControlServiceProtocol(Protocol):
    async def list_gpu_controls(self) -> JSONDict: ...
    async def set_gpu_controls(
        self,
        *,
        device_id: str,
        settings: JSONDict,
        created_by_user_id: int,
    ) -> JSONDict: ...


class HardwareMonitoringCoordinatorProtocol(Protocol):
    def dispatch_snapshot(self, info: JSONDict, loop: asyncio.AbstractEventLoop | None) -> None: ...


class GpuSlotStorageManagerProtocol(Protocol):
    logger: LoggerProtocol

    @property
    def lock(self) -> threading.RLock: ...
    def read_payload(self) -> tuple[JSONDict, bool]: ...
    def write_payload(self, payload: JSONDict) -> None: ...


class GetGpuInfoCallable(Protocol):
    def __call__(self, detailed: bool = True) -> JSONDict: ...


class DatabaseHardwareProtocol(DatabaseSoAIBenchProtocol, Protocol):
    core: DatabaseCoreProtocol

    async def log_hardware_metrics(self, info: JSONDict) -> None: ...
    async def prune_old_hardware_metrics(self, retention_hours: int) -> None: ...
    async def get_latest_network_speed_snapshot(self) -> JSONDict: ...
    async def get_latest_speed_test_snapshot(self) -> JSONDict | None: ...
    async def upsert_speed_test(
        self,
        cache_key: str,
        path: str,
        sample_bytes: int,
        observed_at_ms: int,
        duration_ms: int,
        bytes_processed: int,
        bytes_per_second: float,
    ) -> None: ...
    async def get_speed_test(self, cache_key: str) -> JSONDict | None: ...
    async def save_real_download_speed(
        self,
        plugin_name: str,
        model_id: str,
        bytes_downloaded: int,
        duration_ms: int,
        bytes_per_second: float,
    ) -> None: ...
    async def get_median_real_download_speed(self) -> JSONDict | None: ...
    async def get_historical_hardware_data(
        self,
        component: str,
        start_ts_ms: int,
        end_ts_ms: int,
        interval_ms: int,
        aggregation: str,
        max_points: int,
        identifier: str | None = None,
    ) -> JSONDict: ...


class NvApiClocksProtocol(Protocol):
    def __init__(self, *, core: int, memory: int) -> None: ...

    core: int
    memory: int


class NvApiOverclockProtocol(Protocol):
    core: int | float | None
    memory: int | float | None


class NvApiGpuProtocol(Protocol):
    handle: int
    name: str
    fan: int | float | None
    power_limit: int | float | None

    def get_overclock(self) -> NvApiOverclockProtocol | None: ...

    def set_overclock(self, clocks: NvApiClocksProtocol) -> None: ...


class NvApiSupportProtocol(Protocol):
    @property
    def can_attempt(self) -> bool: ...

    @property
    def available(self) -> bool: ...

    @property
    def status_message(self) -> str | None: ...

    def ensure_initialized(self) -> bool: ...

    def get_phys_gpu(self, vendor_id: int) -> NvApiGpuProtocol | None: ...

    def build_clocks(self, *, core: int, memory: int) -> NvApiClocksProtocol | None: ...

    def restore_coolers(self, handle: int) -> None: ...


class NvmlGateProtocol(Protocol):
    @property
    def logger(self) -> TraceLogger: ...

    @property
    def runtime_platform(self) -> RuntimePlatformViewProtocol: ...

    @property
    def nvapi_support(self) -> NvApiSupportProtocol: ...

    @property
    def nvidia_settings_available(self) -> bool: ...

    @property
    def nvidia_settings_status_message(self) -> str | None: ...

    @property
    def nvml_available(self) -> bool: ...

    def session(self) -> AbstractContextManager[None]: ...


class NvidiaCapabilitiesCacheServiceProtocol(Protocol):
    def get_cached(self, vendor_id: int) -> JSONDict | None: ...

    def set_cached(self, vendor_id: int, payload: JSONDict) -> None: ...

    def invalidate(self, vendor_id: int) -> None: ...

    def clear(self) -> None: ...

    def compute_or_wait(self, vendor_id: int, compute: Callable[[], JSONDict]) -> JSONDict: ...

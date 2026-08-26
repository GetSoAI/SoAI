"""SoAI - Hardware manager entrypoint service [backend/hardware/manager/hardware_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING, override

from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.runtime.protocols import Shutdownable
from core.types.protocols import HttpClientProtocol
from hardware.cpu_rapl import RaplEnergyCache
from hardware.info_network import get_network_info
from hardware.manager.computed_config import (
    HardwareManagerComputedConfig,
    compute_hardware_manager_config,
)
from hardware.manager.dependencies import HardwareManagerDependencies
from hardware.manager.historical_data_query import query_historical_data
from hardware.manager.manager_state import HardwareManagerState
from hardware.manager.monitoring_lifecycle import (
    shutdown_hardware_monitoring,
    start_hardware_monitoring,
)
from hardware.manager.system_capabilities import sync_get_system_capabilities
from hardware.manager.system_info_query import sync_query_system_info
from hardware.manager.variant_support_context import build_variant_support_context

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.hardware.protocols import (
        DatabaseHardwareProtocol,
        HardwareGpuTuningProtocol,
        HardwareMonitoringCoordinatorProtocol,
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.hardware.variant_support import VariantSupportContext
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.internal_protocols import (
        GpuCapabilitiesServiceProtocol,
        GPUInfoCacheServiceProtocol,
        GPUVendorDetectionServiceProtocol,
    )

__all__ = ("HardwareManager",)

LOGGER_NAME = "SoAI.hardware.manager.hardware_manager"


class HardwareManager(Shutdownable):
    get_network_info = staticmethod(get_network_info)

    def __init__(self, deps: HardwareManagerDependencies) -> None:
        self._deps = deps
        self.enabled = bool(deps.settings.enabled)
        self.monitoring_interval_ms = int(deps.settings.monitoring_interval_ms)
        self.cache_ttl = float(deps.settings.cache_ttl)
        self.detailed_gpu_info = bool(deps.settings.detailed_gpu_info)
        self.min_specs_enabled = bool(deps.settings.min_specs_enabled)
        self.history_config = deps.settings.history_config
        self.logger: TraceLogger = get_logger(LOGGER_NAME)
        self._computed: HardwareManagerComputedConfig = compute_hardware_manager_config(deps)
        self.base_dir = self._computed.base_dir
        self.state = HardwareManagerState()
        self.main_loop: asyncio.AbstractEventLoop | None = self.state.main_loop
        self.monitoring_stop_event: threading.Event = self.state.monitoring_stop_event
        self.last_network_stats: dict[str, JSONDict] = self.state.last_network_stats
        self.cached_disk_speed: JSONDict | None = None
        self.disk_speed_cache_timestamp: float = 0.0
        self.cached_disk_speed, self.disk_speed_cache_timestamp = self.state.disk_speed_cache.get()
        self.disk_speed_cache_timestamp = float(self.disk_speed_cache_timestamp)
        self.cached_network_speed: JSONDict = {}
        self.network_speed_cache_timestamp: float = 0.0
        self.loaded_network_speed_from_db: bool = False
        (
            self.cached_network_speed,
            self.network_speed_cache_timestamp,
            self.loaded_network_speed_from_db,
        ) = self.state.network_speed_cache.get()
        self.network_speed_cache_timestamp = float(self.network_speed_cache_timestamp)
        self.loaded_network_speed_from_db = bool(self.loaded_network_speed_from_db)
        self._rapl_energy_cache: RaplEnergyCache = RaplEnergyCache()
        self.network_speed_cache_ttl_seconds: float = float(
            deps.settings.network_speed_cache_ttl_seconds,
        )
        self._event_bus: EventBusProtocol | None = deps.event_bus
        self.database_hardware: DatabaseHardwareProtocol | None = deps.database_hardware
        self.monitoring_coordinator: HardwareMonitoringCoordinatorProtocol = (
            deps.monitoring_coordinator
        )
        self.hw_gpu_tuning: HardwareGpuTuningProtocol = deps.hw_gpu_tuning
        self._executor: CommandExecutorProtocol = deps.command_executor
        self._gpu_info_cache_service: GPUInfoCacheServiceProtocol = deps.gpu_info_cache_service
        self._gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol = (
            deps.gpu_vendor_detection_service
        )
        self._gpu_capabilities_service: GpuCapabilitiesServiceProtocol = (
            deps.gpu_capabilities_service
        )
        self._nvidia_nvml_gate: NvmlGateProtocol = deps.nvidia_nvml_gate
        self._nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol = (
            deps.nvidia_capabilities_cache_service
        )

    @property
    def nvidia_nvml_gate(self) -> NvmlGateProtocol:
        return self._nvidia_nvml_gate

    def sync_get_system_info(
        self,
        *,
        cache: bool,
        include_gpu_capabilities: bool = True,
    ) -> JSONDict:
        return sync_query_system_info(
            state=self.state,
            manager=self,
            executor=self._executor,
            logger=self.logger,
            hw_gpu_tuning=self.hw_gpu_tuning,
            cache_ttl_seconds=self.cache_ttl,
            monitoring_interval_ms=self.monitoring_interval_ms,
            history_config=self.history_config,
            history_enabled=self._computed.history_enabled,
            detailed_gpu_info=self.detailed_gpu_info,
            gpu_info_cache_service=self._gpu_info_cache_service,
            gpu_vendor_detection_service=self._gpu_vendor_detection_service,
            nvidia_nvml_gate=self._nvidia_nvml_gate,
            nvidia_capabilities_cache_service=self._nvidia_capabilities_cache_service,
            rapl_energy_cache=self._rapl_energy_cache,
            components=None,
            cache=cache,
            include_gpu_capabilities=include_gpu_capabilities,
        )

    async def get_system_info(
        self,
        components: Sequence[str] | None = None,
        cache: bool = True,
        include_gpu_capabilities: bool = True,
    ) -> JSONDict:
        return await asyncio.to_thread(
            sync_query_system_info,
            state=self.state,
            manager=self,
            executor=self._executor,
            logger=self.logger,
            hw_gpu_tuning=self.hw_gpu_tuning,
            cache_ttl_seconds=self.cache_ttl,
            monitoring_interval_ms=self.monitoring_interval_ms,
            history_config=self.history_config,
            history_enabled=self._computed.history_enabled,
            detailed_gpu_info=self.detailed_gpu_info,
            gpu_info_cache_service=self._gpu_info_cache_service,
            gpu_vendor_detection_service=self._gpu_vendor_detection_service,
            nvidia_nvml_gate=self._nvidia_nvml_gate,
            nvidia_capabilities_cache_service=self._nvidia_capabilities_cache_service,
            rapl_energy_cache=self._rapl_energy_cache,
            components=components,
            cache=cache,
            include_gpu_capabilities=include_gpu_capabilities,
        )

    async def get_system_capabilities(self) -> JSONDict:
        return await asyncio.to_thread(
            sync_get_system_capabilities,
            executor=self._executor,
            logger=self.logger,
            monitoring_interval_ms=self.monitoring_interval_ms,
            history_config=self.history_config,
            history_enabled=self._computed.history_enabled,
            gpu_info_cache_service=self._gpu_info_cache_service,
            gpu_vendor_detection_service=self._gpu_vendor_detection_service,
            nvidia_nvml_gate=self._nvidia_nvml_gate,
            nvidia_capabilities_cache_service=self._nvidia_capabilities_cache_service,
            rapl_energy_cache=self._rapl_energy_cache,
            gpu_info=None,
        )

    async def get_gpu_capabilities(self) -> JSONDict:
        return await self._gpu_capabilities_service.get_capabilities(
            self.hw_gpu_tuning.enrich_gpu_capabilities,
        )

    async def build_variant_support_context(
        self,
        models_dir: str | None,
        include_speed_tests: bool,
        *,
        database_hardware: DatabaseHardwareProtocol | None = None,
        http_client: HttpClientProtocol | None = None,
    ) -> VariantSupportContext:
        return await build_variant_support_context(
            deps=self._deps,
            computed=self._computed,
            models_dir=models_dir,
            include_speed_tests=include_speed_tests,
            get_system_capabilities=self.get_system_capabilities,
            database_hardware=database_hardware,
            http_client=http_client,
        )

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
    ) -> JSONDict:
        return await query_historical_data(
            logger=self.logger,
            history_enabled=self._computed.history_enabled,
            database_hardware=self.database_hardware,
            history_config=self.history_config,
            monitoring_interval_ms=self.monitoring_interval_ms,
            last_full_info=self.state.last_full_info,
            get_system_info=self.get_system_info,
            executor=self._executor,
            gpu_info_cache_service=self._gpu_info_cache_service,
            gpu_vendor_detection_service=self._gpu_vendor_detection_service,
            nvidia_nvml_gate=self._nvidia_nvml_gate,
            nvidia_capabilities_cache_service=self._nvidia_capabilities_cache_service,
            start_ts_ms=start_ts_ms,
            end_ts_ms=end_ts_ms,
            points=points,
            interval_ms=interval_ms,
            aggregation=aggregation,
            component=component,
            gpu_index=gpu_index,
            identifier=identifier,
        )

    async def start_monitoring(self) -> bool:
        started = start_hardware_monitoring(
            manager=self,
            min_specs_manager=self,
            state=self.state,
            enabled=self.enabled,
            hw_gpu_tuning_set_main_loop=self.hw_gpu_tuning.set_main_loop,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            executor=self._executor,
            logger=self.logger,
            rapl_energy_cache=self._rapl_energy_cache,
            min_specs_enabled=self.min_specs_enabled,
        )
        self.main_loop = self.state.main_loop
        return started

    @override
    async def shutdown(self) -> None:
        await shutdown_hardware_monitoring(state=self.state, logger=self.logger)

    def set_disk_speed_cache(self, snapshot: JSONDict | None, *, cached_at: float) -> None:
        self.state.disk_speed_cache.set(snapshot, cached_at=cached_at)
        self.cached_disk_speed = snapshot
        self.disk_speed_cache_timestamp = float(cached_at)

    def set_network_speed_cache(
        self,
        snapshot: JSONDict,
        *,
        cached_at: float,
        loaded_from_db: bool,
    ) -> None:
        self.state.network_speed_cache.set(
            snapshot,
            cached_at=cached_at,
            loaded_from_db=loaded_from_db,
        )
        self.cached_network_speed = snapshot
        self.network_speed_cache_timestamp = float(cached_at)
        self.loaded_network_speed_from_db = bool(loaded_from_db)

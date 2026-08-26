"""SoAI - Disabled hardware manager [backend/hardware/manager/null_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import platform
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.di.validation import require_dependencies
from core.hardware.protocols import DatabaseHardwareProtocol, NvmlGateProtocol
from core.hardware.variant_support import VariantSupportContext
from core.logging.protocols import TraceLogger
from core.runtime.platform import get_runtime_platform
from core.timing.epoch import epoch_ms
from core.types.protocols import HttpClientProtocol
from core.validation.coercion import coerce_float_with_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "NullHardwareManager",
    "NullHardwareManagerDependencies",
)


@dataclass(frozen=True, slots=True)
class NullHardwareManagerDependencies:
    logger: TraceLogger
    nvidia_nvml_gate: NvmlGateProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="NullHardwareManagerDependencies",
            logger=self.logger,
            nvidia_nvml_gate=self.nvidia_nvml_gate,
        )


class NullHardwareManager:
    def __init__(self, deps: NullHardwareManagerDependencies) -> None:
        self.enabled: bool = False
        self.logger: TraceLogger = deps.logger
        self._nvidia_nvml_gate: NvmlGateProtocol = deps.nvidia_nvml_gate
        self.history_config: Mapping[str, JSONValue] = {
            "ENABLED": False,
            "DB_RETENTION_HOURS": 0,
            "MAX_POINTS": 0,
            "LOGGING_INTERVAL_MS": 0,
            "SUPPORTED_INTERVALS_MS": [],
            "DEFAULT_INTERVAL_MS": 0,
            "SUPPORTED_AGGREGATIONS": ["avg", "ohlc"],
        }

    @property
    def nvidia_nvml_gate(self) -> NvmlGateProtocol:
        return self._nvidia_nvml_gate

    def get_network_info(self) -> JSONDict:
        return {}

    async def get_system_capabilities(self) -> JSONDict:
        runtime_platform = get_runtime_platform()
        system_ram_gb = round(psutil.virtual_memory().total / 1024**3, 2)
        total_vram_gb = 0.0
        history_enabled = False
        return {
            "platform": runtime_platform.os_id or platform.system() or "Unknown",
            "arch": runtime_platform.architecture_id or runtime_platform.architecture,
            "platform_id": runtime_platform.platform_id,
            "system_ram_gb": system_ram_gb,
            "total_vram_gb": total_vram_gb,
            "total_system_memory_gb": round(system_ram_gb + total_vram_gb, 2),
            "monitoring_interval_ms": 0,
            "history_retention_hours": 0,
            "history_config": {
                "enabled": history_enabled,
                "retention_hours": 0,
                "max_points": 0,
                "logging_interval_ms": 0,
                "supported_intervals_ms": [],
                "default_interval_ms": 0,
                "supported_aggregations": ["avg", "ohlc"],
                "components": ["cpu", "gpu", "disk", "network"],
            },
        }

    async def get_system_info(
        self,
        components: Sequence[str] | None = None,
        cache: bool = True,
        include_gpu_capabilities: bool = True,
    ) -> JSONDict:
        _ = (components, cache, include_gpu_capabilities)
        capabilities = await self.get_system_capabilities()
        system_ram_gb = coerce_float_with_bool(capabilities.get("system_ram_gb")) or 0.0
        total_vram_gb = coerce_float_with_bool(capabilities.get("total_vram_gb")) or 0.0
        summary: JSONDict = {
            "total_system_ram_gb": system_ram_gb,
            "total_vram_gb": total_vram_gb,
            "total_system_memory_gb": round(system_ram_gb + total_vram_gb, 2),
        }
        return {
            "timestamp_ms": epoch_ms(),
            "summary": summary,
            "capabilities": capabilities,
        }

    async def get_gpu_capabilities(self) -> JSONDict:
        return {}

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
        _ = (
            start_ts_ms,
            end_ts_ms,
            points,
            interval_ms,
            aggregation,
            component,
            gpu_index,
            identifier,
        )
        return {}

    async def build_variant_support_context(
        self,
        models_dir: str | None,
        include_speed_tests: bool,
        *,
        database_hardware: DatabaseHardwareProtocol | None = None,
        http_client: HttpClientProtocol | None = None,
    ) -> VariantSupportContext:
        _ = (models_dir, include_speed_tests, database_hardware, http_client)
        return VariantSupportContext(
            disk_free_bytes=None,
            disk_speed_template=None,
            network_speed_template=None,
            available_vram_gb=None,
            total_memory_gb=None,
            system_ram_gb=None,
        )

    async def start_monitoring(self) -> bool:
        return False

    async def shutdown(self) -> None:
        return

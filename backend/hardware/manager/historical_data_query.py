"""SoAI - Hardware manager historical metrics query [backend/hardware/manager/historical_data_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.manager.gpu_device_resolution import resolve_gpu_device_id
from hardware.manager.history_queries import get_historical_data

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from core.hardware.protocols import (
        DatabaseHardwareProtocol,
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue
    from hardware.internal_protocols import (
        GPUInfoCacheServiceProtocol,
        GPUVendorDetectionServiceProtocol,
    )

__all__ = ("query_historical_data",)


async def query_historical_data(
    *,
    logger: TraceLogger,
    history_enabled: bool,
    database_hardware: DatabaseHardwareProtocol | None,
    history_config: Mapping[str, JSONValue],
    monitoring_interval_ms: int,
    last_full_info: JSONDict,
    get_system_info: Callable[[list[str] | None, bool], Awaitable[JSONDict]],
    executor: CommandExecutorProtocol,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    start_ts_ms: int,
    end_ts_ms: int,
    points: int,
    interval_ms: int,
    aggregation: str,
    component: str,
    gpu_index: int | None,
    identifier: str | None,
) -> JSONDict:
    def device_id_resolver(idx: int) -> str | None:
        return resolve_gpu_device_id(
            idx,
            executor,
            gpu_info_cache_service,
            gpu_vendor_detection_service,
            nvidia_nvml_gate,
            nvidia_capabilities_cache_service,
        )

    return await get_historical_data(
        logger=logger,
        history_enabled=history_enabled,
        database_hardware=database_hardware,
        history_config=history_config,
        monitoring_interval_ms=monitoring_interval_ms,
        last_full_info=last_full_info,
        get_system_info=get_system_info,
        resolve_gpu_device_id=device_id_resolver,
        component=component,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        points=points,
        gpu_index=gpu_index,
        identifier=identifier,
        interval_ms=interval_ms,
        aggregation=aggregation,
    )

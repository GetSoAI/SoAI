"""SoAI - GPU slot capability and inventory helpers [backend/hardware/gpu_tuning/slot_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.presets.inventory_snapshot import snapshot_gpu_inventory
from hardware.probe import async_get_raw_capabilities, sync_get_raw_capabilities

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "async_get_tuning_capabilities",
    "get_tuning_capabilities_for_services",
    "snapshot_tuning_inventory",
)


def snapshot_tuning_inventory(
    *,
    executor: CommandExecutorProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
) -> dict[str, JSONDict]:
    return snapshot_gpu_inventory(
        executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_info_cache_service=gpu_services.gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_services.gpu_vendor_detection_service,
        nvidia_nvml_gate=gpu_services.nvidia_nvml_gate,
        nvidia_capabilities_cache_service=gpu_services.nvidia_capabilities_cache_service,
    )


def get_tuning_capabilities_for_services(
    *,
    executor: CommandExecutorProtocol,
    gpu_services: GpuServiceDependencies,
    logger: TraceLogger,
) -> JSONDict:
    return sync_get_raw_capabilities(
        executor,
        gpu_info_cache_service=gpu_services.gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_services.gpu_vendor_detection_service,
        nvidia_nvml_gate=gpu_services.nvidia_nvml_gate,
        nvidia_capabilities_cache_service=gpu_services.nvidia_capabilities_cache_service,
        logger=logger,
        nvidia_settings_controller=gpu_services.nvidia_settings_controller,
    )


async def async_get_tuning_capabilities(
    *,
    executor: CommandExecutorProtocol,
    gpu_services: GpuServiceDependencies,
    logger: TraceLogger,
) -> JSONDict:
    return await async_get_raw_capabilities(
        executor,
        gpu_info_cache_service=gpu_services.gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_services.gpu_vendor_detection_service,
        nvidia_nvml_gate=gpu_services.nvidia_nvml_gate,
        nvidia_capabilities_cache_service=gpu_services.nvidia_capabilities_cache_service,
        logger=logger,
        nvidia_settings_controller=gpu_services.nvidia_settings_controller,
    )

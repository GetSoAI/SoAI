"""SoAI - NVIDIA GPU tuning primitives [backend/hardware/vendors/nvidia/tuning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.gpu_operation_results import build_gpu_result
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest
from hardware.vendors.nvidia.metrics import sync_get_nvidia_capabilities
from hardware.vendors.nvidia.smi import NvidiaSettingsController
from hardware.vendors.nvidia.tuning_nvapi import sync_set_nvidia_settings_nvapi
from hardware.vendors.nvidia.tuning_nvidia_settings import (
    sync_set_nvidia_settings_via_nvidia_settings,
)
from hardware.vendors.nvidia.tuning_nvml import sync_set_nvidia_settings_via_nvml

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = ("sync_set_nvidia_settings",)


def sync_set_nvidia_settings(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    request: GpuSettingsApplyRequest,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    nvidia_settings_controller: NvidiaSettingsController | None = None,
    capabilities: JSONDict | None = None,
) -> JSONDict:
    control_backend = request.control_backend
    if control_backend is None:
        return build_gpu_result(errors=["NVIDIA control backend is required."])
    caps = capabilities or sync_get_nvidia_capabilities(
        logger,
        vendor_id,
        nvml_gate=nvml_gate,
        capabilities_cache_service=capabilities_cache_service,
    )
    if control_backend == "nvidia_nvapi":
        return sync_set_nvidia_settings_nvapi(
            logger,
            vendor_id,
            request=request,
            capabilities=caps,
            nvml_gate=nvml_gate,
            capabilities_cache_service=capabilities_cache_service,
        )
    if control_backend == "nvidia_settings":
        return sync_set_nvidia_settings_via_nvidia_settings(
            logger,
            vendor_id,
            nvidia_settings_controller,
            request=request,
            capabilities=caps,
            nvml_gate=nvml_gate,
            capabilities_cache_service=capabilities_cache_service,
        )
    if control_backend != "nvidia_nvml":
        return build_gpu_result(
            errors=[f"NVIDIA control backend '{control_backend}' is unsupported."],
        )
    return sync_set_nvidia_settings_via_nvml(
        logger,
        vendor_id,
        request=request,
        capabilities=caps,
        nvml_gate=nvml_gate,
        capabilities_cache_service=capabilities_cache_service,
    )

"""SoAI - NVIDIA NVML/NvAPI environment assembly helpers [backend/app/composition/nvidia_nvml_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from dataclasses import dataclass

from core.concurrency.singleflight import SyncSingleflight
from core.hardware.protocols import NvmlGateProtocol
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from hardware.vendors.nvidia import nvml
from hardware.vendors.nvidia.nvapi_runtime import DeferredNvApiSupport
from hardware.vendors.nvidia.nvml_preflight import NvmlRuntimeStatus
from hardware.vendors.nvidia.persistence import (
    NvidiaCapabilitiesCacheService,
    NvidiaCapabilitiesCacheServiceDependencies,
)
from hardware.vendors.nvidia.settings_support import detect_nvidia_settings_available

__all__ = (
    "NvidiaNvmlEnvironment",
    "create_nvidia_nvml_environment",
)

LOGGER_NAME = "SoAI.app.composition.nvidia_nvml_environment"


@dataclass(frozen=True, slots=True)
class NvidiaNvmlEnvironment:
    nvml_gate: NvmlGateProtocol
    capabilities_cache_service: NvidiaCapabilitiesCacheService


def create_nvidia_nvml_environment(
    *,
    nvml_runtime_status: NvmlRuntimeStatus,
) -> NvidiaNvmlEnvironment:
    runtime_platform = get_runtime_platform()
    nvidia_logger = get_logger(LOGGER_NAME)
    if nvml_runtime_status.probe_failed:
        nvidia_logger.warning(
            (
                "NVML is disabled because the isolated NVML preflight failed (%s, exit %s): %s. "
                "NVIDIA monitoring and control fall back to nvidia-smi."
            ),
            nvml_runtime_status.outcome.value,
            nvml_runtime_status.return_code,
            nvml_runtime_status.detail,
        )
    else:
        nvidia_logger.trace(
            "NVML preflight outcome: %s (%s)",
            nvml_runtime_status.outcome.value,
            nvml_runtime_status.detail,
        )
    nvidia_settings_available, nvidia_settings_status_message = detect_nvidia_settings_available(
        runtime_platform,
    )
    if nvidia_settings_available:
        nvidia_logger.trace("nvidia-settings found for Linux NVIDIA GPU control")
    elif nvidia_settings_status_message and runtime_platform.is_linux:
        nvidia_logger.trace("nvidia-settings disabled: %s", nvidia_settings_status_message)
    capabilities_cache_service = NvidiaCapabilitiesCacheService(
        NvidiaCapabilitiesCacheServiceDependencies(
            entries={},
            entries_lock=threading.Lock(),
            singleflight=SyncSingleflight(),
        ),
    )
    nvapi_support = DeferredNvApiSupport(
        logger=nvidia_logger,
        runtime_platform=runtime_platform,
    )
    if nvapi_support.status_message and runtime_platform.is_windows:
        nvidia_logger.trace("NvAPI disabled: %s", nvapi_support.status_message)
    return NvidiaNvmlEnvironment(
        nvml_gate=nvml.NvmlGate(
            logger=nvidia_logger,
            runtime_platform=runtime_platform,
            nvapi_support=nvapi_support,
            nvidia_settings_available=nvidia_settings_available,
            nvidia_settings_status_message=nvidia_settings_status_message,
            nvml_available=nvml_runtime_status.usable,
        ),
        capabilities_cache_service=capabilities_cache_service,
    )

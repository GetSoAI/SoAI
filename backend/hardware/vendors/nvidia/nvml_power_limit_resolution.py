"""SoAI - NVML power-limit function resolution from pynvml module [backend/hardware/vendors/nvidia/nvml_power_limit_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from types import ModuleType

from hardware.vendors.nvidia.internal_protocols import (
    NvmlDeviceGetPowerManagementDefaultLimitProtocol,
    NvmlDeviceSetPowerManagementLimitProtocol,
)

__all__ = ("resolve_nvml_power_limit_functions",)


def resolve_nvml_power_limit_functions(
    pynvml_module: ModuleType,
) -> tuple[
    NvmlDeviceGetPowerManagementDefaultLimitProtocol | None,
    NvmlDeviceSetPowerManagementLimitProtocol | None,
]:
    try:
        default_limit_value = pynvml_module.nvmlDeviceGetPowerManagementDefaultLimit
    except AttributeError:
        default_limit_value = None
    try:
        set_limit_value = pynvml_module.nvmlDeviceSetPowerManagementLimit
    except AttributeError:
        set_limit_value = None

    power_default_limit_function = (
        default_limit_value
        if isinstance(default_limit_value, NvmlDeviceGetPowerManagementDefaultLimitProtocol)
        else None
    )
    power_set_limit_function = (
        set_limit_value
        if isinstance(set_limit_value, NvmlDeviceSetPowerManagementLimitProtocol)
        else None
    )
    return power_default_limit_function, power_set_limit_function

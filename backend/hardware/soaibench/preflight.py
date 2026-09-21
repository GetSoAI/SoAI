"""SoAI - SoAIBench OpenCL preflight flow [backend/hardware/soaibench/preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.soaibench.device_matching import match_opencl_device
from hardware.soaibench.errors import SoAIBenchUnsupported
from hardware.soaibench.opencl_devices import enumerate_opencl_gpu_devices
from hardware.soaibench.types import SoAIBenchGpuIdentity
from hardware.vendors.vendor_metadata import vendor_aliases
from hardware.vendors.vendor_types import NVIDIA_VENDOR

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.internal_protocols import SoAIBenchOpenCLExecutionProtocol

__all__ = ("preflight_blocking", "run_preflight")


async def run_preflight(
    *,
    opencl_pool: SoAIBenchOpenCLExecutionProtocol,
    identity: SoAIBenchGpuIdentity,
) -> JSONDict:
    return await opencl_pool.preflight(identity, timeout_sec=10.0)


def preflight_blocking(identity: SoAIBenchGpuIdentity) -> JSONDict:
    _validate_driver_binding(identity)
    candidates = enumerate_opencl_gpu_devices()
    match = match_opencl_device(identity, candidates)
    return {
        "match_basis": match.match_basis,
        "opencl_platform_name": match.device.platform_name,
        "opencl_platform_vendor": match.device.platform_vendor,
        "opencl_device_name": match.device.device_name,
        "opencl_device_vendor": match.device.device_vendor,
        "opencl_driver_version": match.device.driver_version,
    }


def _validate_driver_binding(identity: SoAIBenchGpuIdentity) -> None:
    if NVIDIA_VENDOR not in vendor_aliases(identity.vendor or ""):
        return
    if identity.kernel_driver == "nvidia":
        return
    operating_system = (identity.operating_system or "").strip().lower()
    if operating_system and operating_system != "linux":
        return
    raise SoAIBenchUnsupported(
        reason="gpu_driver_inactive",
        message=(
            "The selected NVIDIA GPU is present on PCIe but is not bound to the "
            "active NVIDIA kernel driver."
        ),
    )

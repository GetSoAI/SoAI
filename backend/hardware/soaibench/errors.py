"""SoAI - SoAIBench V1 stable failure reasons [backend/hardware/soaibench/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "SoAIBenchUnsupported",
    "unsupported_guidance",
)


class SoAIBenchUnsupported(Exception):
    reason: str
    message: str

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(reason, message)
        self.reason = reason
        self.message = message


def unsupported_guidance(reason: str) -> str:
    if reason == "opencl_loader_missing":
        return (
            "Install or update the vendor GPU driver with OpenCL support. "
            "On Linux, install the OpenCL ICD loader and the vendor GPU OpenCL ICD."
        )
    if reason == "opencl_platform_unavailable":
        return "Install a vendor OpenCL ICD so the system OpenCL loader exposes a platform."
    if reason == "opencl_runtime_error":
        return "Verify the selected GPU driver and OpenCL runtime are responsive."
    if reason == "opencl_gpu_device_unavailable":
        return "Install a vendor OpenCL runtime that exposes a GPU device."
    if reason == "opencl_device_match_missing":
        return "Install or update the selected GPU vendor driver so OpenCL exposes the same GPU."
    if reason == "opencl_device_match_ambiguous":
        return "OpenCL exposed multiple matching GPUs; select a GPU with a unique UUID or PCI identity."
    if reason == "gpu_driver_inactive":
        return (
            "Install a compatible GPU driver and reboot so the selected GPU binds to that driver."
        )
    if reason == "hardware_manager_unavailable":
        return "Enable hardware monitoring before starting SoAIBench."
    if reason == "gpu_inventory_unavailable":
        return "Refresh GPU inventory before starting SoAIBench."
    return "SoAIBench is unsupported on the selected GPU in the current runtime."

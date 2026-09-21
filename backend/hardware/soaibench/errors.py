"""SoAI - SoAIBench stable failure reasons [backend/hardware/soaibench/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.types.json import JSONDict

__all__ = (
    "SoAIBenchUnsupported",
    "SoAIBenchRunningWithoutOwner",
    "SoAIBenchCompanionFailure",
    "SoAIBenchCompanionFinalizationError",
    "SoAIBenchHeartbeatSuperseded",
    "unsupported_guidance",
)


class SoAIBenchUnsupported(Exception):
    reason: str
    message: str
    diagnostic: str | None

    def __init__(self, reason: str, message: str, diagnostic: str | None = None) -> None:
        super().__init__(reason, message, diagnostic)
        self.reason = reason
        self.message = message
        self.diagnostic = diagnostic


class SoAIBenchRunningWithoutOwner(StateError):
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class SoAIBenchCompanionFailure:
    code: str
    exception: BaseException


class SoAIBenchCompanionFinalizationError(Exception):
    durable_run: JSONDict
    failures: tuple[SoAIBenchCompanionFailure, ...]

    def __init__(
        self,
        durable_run: JSONDict,
        failures: tuple[SoAIBenchCompanionFailure, ...],
    ) -> None:
        super().__init__(durable_run, failures)
        self.durable_run = durable_run
        self.failures = failures


class SoAIBenchHeartbeatSuperseded(Exception):
    durable_run: JSONDict

    def __init__(self, durable_run: JSONDict) -> None:
        super().__init__(durable_run)
        self.durable_run = durable_run


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
    if reason == "opencl_device_identity_conflict":
        return "Refresh GPU inventory and update the vendor driver before retrying SoAIBench."
    if reason == "gpu_driver_inactive":
        return (
            "Install a compatible GPU driver and reboot so the selected GPU binds to that driver."
        )
    if reason == "hardware_manager_unavailable":
        return "Enable hardware monitoring before starting SoAIBench."
    if reason == "gpu_inventory_unavailable":
        return "Refresh GPU inventory before starting SoAIBench."
    return "SoAIBench is unsupported on the selected GPU in the current runtime."

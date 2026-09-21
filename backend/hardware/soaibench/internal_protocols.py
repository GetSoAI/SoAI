"""SoAI - SoAIBench internal protocol definitions [backend/hardware/soaibench/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from hardware.vendors.nvidia.internal_protocols import NvmlPciInfoProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.soaibench.types import SoAIBenchGpuIdentity
    from hardware.soaibench.workload_common import SoAIBenchPhaseResult

__all__ = (
    "MAX_CHILD_MESSAGE_BYTES",
    "NvidiaClockEventNvmlModuleProtocol",
    "NvidiaPowerNvmlModuleProtocol",
    "NvidiaTelemetryNvmlModuleProtocol",
    "NvidiaTemperatureNvmlModuleProtocol",
    "NvidiaThrottleNvmlModuleProtocol",
    "NvidiaUtilizationNvmlModuleProtocol",
    "NvidiaUtilizationProtocol",
    "SoAIBenchOpenCLExecutionProtocol",
    "SoAIBenchPublicationProtocol",
)

MAX_CHILD_MESSAGE_BYTES = 64 * 1024


class SoAIBenchPublicationProtocol(Protocol):
    async def preview(self, *, run_id: str, user_id: int) -> JSONDict: ...

    async def publish(self, *, run_id: str, user_id: int) -> tuple[int, JSONDict]: ...


@runtime_checkable
class NvidiaTelemetryNvmlModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlDeviceGetCount: Callable[[], int]
    nvmlDeviceGetHandleByIndex: Callable[[int], ctypes.c_void_p]
    nvmlDeviceGetPciInfo: Callable[[ctypes.c_void_p], NvmlPciInfoProtocol]


@runtime_checkable
class NvidiaTemperatureNvmlModuleProtocol(Protocol):
    NVMLError: type[Exception]
    NVML_TEMPERATURE_GPU: int
    nvmlDeviceGetTemperature: Callable[[ctypes.c_void_p, int], int]


@runtime_checkable
class NvidiaPowerNvmlModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlDeviceGetPowerUsage: Callable[[ctypes.c_void_p], int]


class NvidiaUtilizationProtocol(Protocol):
    gpu: int


@runtime_checkable
class NvidiaUtilizationNvmlModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlDeviceGetUtilizationRates: Callable[[ctypes.c_void_p], NvidiaUtilizationProtocol]


@runtime_checkable
class NvidiaClockEventNvmlModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlClocksEventReasonNone: int
    nvmlDeviceGetCurrentClocksEventReasons: Callable[[ctypes.c_void_p], int]


@runtime_checkable
class NvidiaThrottleNvmlModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlClocksThrottleReasonNone: int
    nvmlDeviceGetCurrentClocksThrottleReasons: Callable[[ctypes.c_void_p], int]


class SoAIBenchOpenCLExecutionProtocol(Protocol):
    @property
    def degraded(self) -> bool: ...

    async def close(self) -> None: ...

    async def preflight(
        self,
        identity: SoAIBenchGpuIdentity,
        *,
        timeout_sec: float,
    ) -> JSONDict: ...

    async def phase(
        self,
        name: str,
        identity: SoAIBenchGpuIdentity,
        *,
        stress: bool,
        timeout_sec: float,
    ) -> SoAIBenchPhaseResult: ...

"""SoAI - NVIDIA vendor internal protocols [backend/hardware/vendors/nvidia/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import Protocol, runtime_checkable

from core.hardware.protocols import NvApiClocksProtocol, NvApiGpuProtocol

__all__ = (
    "NvApiClocksFactoryProtocol",
    "NvApiFactoryProtocol",
    "NvApiGpuFactoryProtocol",
    "NvApiGpuModuleProtocol",
    "NvApiPythonModuleProtocol",
    "NvApiRuntimeProtocol",
    "NvmlDeviceGetGpcClkMinMaxVfOffsetProtocol",
    "NvmlDeviceGetGpcClkVfOffsetProtocol",
    "NvmlDeviceGetHandleByIndexProtocol",
    "NvmlDeviceGetMemClkMinMaxVfOffsetProtocol",
    "NvmlDeviceGetMemClkVfOffsetProtocol",
    "NvmlDeviceGetMinMaxClockOfPStateProtocol",
    "NvmlDeviceGetNameProtocol",
    "NvmlDeviceGetPciInfoProtocol",
    "NvmlDeviceGetPowerManagementDefaultLimitProtocol",
    "NvmlDeviceSetPowerManagementLimitProtocol",
    "NvmlErrorValueProtocol",
    "NvmlPciInfoProtocol",
    "NvmlProcessInfoProtocol",
    "NvmlSystemGetCudaDriverVersionProtocol",
)


class NvmlProcessInfoProtocol(Protocol):
    pid: int
    usedGpuMemory: int


@runtime_checkable
class NvmlErrorValueProtocol(Protocol):
    value: int


class NvmlPciInfoProtocol(Protocol):
    busId: str | bytes


@runtime_checkable
class NvmlDeviceGetHandleByIndexProtocol(Protocol):
    def __call__(self, index: int, /) -> ctypes.c_void_p: ...


@runtime_checkable
class NvmlDeviceGetNameProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> str | bytes: ...


@runtime_checkable
class NvmlDeviceGetPciInfoProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> NvmlPciInfoProtocol: ...


@runtime_checkable
class NvmlDeviceGetPowerManagementDefaultLimitProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> int: ...


@runtime_checkable
class NvmlDeviceSetPowerManagementLimitProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, limit: int, /) -> None: ...


@runtime_checkable
class NvmlSystemGetCudaDriverVersionProtocol(Protocol):
    def __call__(self) -> int: ...


@runtime_checkable
class NvmlDeviceGetMinMaxClockOfPStateProtocol(Protocol):
    def __call__(
        self,
        handle: ctypes.c_void_p,
        clock_type: int,
        _pstate: int,
        /,
    ) -> tuple[int, int]: ...


@runtime_checkable
class NvmlDeviceGetGpcClkMinMaxVfOffsetProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> tuple[int, int]: ...


@runtime_checkable
class NvmlDeviceGetGpcClkVfOffsetProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> int | None: ...


@runtime_checkable
class NvmlDeviceGetMemClkMinMaxVfOffsetProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> tuple[int, int]: ...


@runtime_checkable
class NvmlDeviceGetMemClkVfOffsetProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> int | None: ...


class NvApiRuntimeProtocol(Protocol):
    gpu_handles: list[int]

    def restore_coolers(self, handle: int) -> None: ...


class NvApiFactoryProtocol(Protocol):
    def __call__(self) -> NvApiRuntimeProtocol: ...


class NvApiGpuFactoryProtocol(Protocol):
    def __call__(self, handle: int, _api: NvApiRuntimeProtocol) -> NvApiGpuProtocol: ...


class NvApiClocksFactoryProtocol(Protocol):
    def __call__(
        self,
        *,
        core: int,
        memory: int,
        processor: int | None,
        video: int | None,
    ) -> NvApiClocksProtocol: ...


@runtime_checkable
class NvApiPythonModuleProtocol(Protocol):
    NvAPI: NvApiFactoryProtocol


@runtime_checkable
class NvApiGpuModuleProtocol(Protocol):
    Gpu: NvApiGpuFactoryProtocol
    Clocks: NvApiClocksFactoryProtocol

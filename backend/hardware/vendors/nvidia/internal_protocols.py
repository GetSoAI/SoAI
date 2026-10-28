"""SoAI - NVIDIA vendor internal protocols [backend/hardware/vendors/nvidia/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, overload, runtime_checkable

from core.errors.exceptions import StateError
from core.system.commands import CommandResult
from hardware.vendors.nvidia.nvapi_fan_types import NvApiFanControl, NvApiFanStatus
from hardware.vendors.nvidia.nvapi_native_types import NvApiPstates
from hardware.vendors.nvidia.nvapi_power_types import NvApiPowerInfo, NvApiPowerStatus

__all__ = (
    "NvApiFactoryProtocol",
    "NvApiRuntimeProtocol",
    "NvmlDeviceGetHandleByIndexProtocol",
    "NvmlDeviceGetMinMaxClockOfPStateProtocol",
    "NvmlDeviceGetNameProtocol",
    "NvmlDeviceGetPciInfoProtocol",
    "NvmlDeviceGetPowerManagementDefaultLimitProtocol",
    "NvmlDeviceSetPowerManagementLimitProtocol",
    "NvmlErrorValueProtocol",
    "NvmlClockOffsetFunctionProtocol",
    "NvmlPciInfoProtocol",
    "NvmlIdentityModuleProtocol",
    "NvmlProcessInfoProtocol",
    "NvmlSystemGetCudaDriverVersionProtocol",
)


if TYPE_CHECKING:
    from hardware.vendors.nvidia.nvml_clock_offset_structure import NvmlClockOffset

    type NvmlDeviceHandle = ctypes.c_void_p | NvmlNativeHandleProtocol
    type NvmlClockOffsetSymbol = Literal["nvmlDeviceGetClockOffsets", "nvmlDeviceSetClockOffsets"]
    type NvmlNativeFunctionSymbol = Literal[
        "nvmlDeviceGetClockOffsets",
        "nvmlDeviceSetClockOffsets",
        "nvmlDeviceSetPowerManagementLimit",
        "nvmlDeviceSetPersistenceMode",
        "nvmlDeviceSetGpcClkVfOffset",
        "nvmlDeviceSetMemClkVfOffset",
        "nvmlDeviceSetApplicationsClocks",
        "nvmlDeviceSetFanSpeed_v2",
        "nvmlDeviceSetDefaultFanSpeed_v2",
    ]
    type NvmlClockOffsetResolver = Callable[
        [NvmlClockOffsetSymbol], NvmlClockOffsetFunctionProtocol
    ]


class NvmlProcessInfoProtocol(Protocol):
    pid: int
    usedGpuMemory: int


@runtime_checkable
class NvmlErrorValueProtocol(Protocol):
    value: int


class NvmlPciInfoProtocol(Protocol):
    busId: str | bytes


@runtime_checkable
class NvmlNativeHandleProtocol(Protocol):
    @property
    def contents(self) -> ctypes.Structure: ...

    def __bool__(self) -> bool: ...


@runtime_checkable
class NvmlArchitectureModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlDeviceGetHandleByPciBusId: Callable[[str], NvmlDeviceHandle]
    nvmlDeviceGetUUID: Callable[[NvmlDeviceHandle], str | bytes]
    nvmlDeviceGetPciInfo: Callable[[NvmlDeviceHandle], NvmlPciInfoProtocol]
    nvmlDeviceGetArchitecture: Callable[[NvmlDeviceHandle], int]


@runtime_checkable
class NvmlIdentityModuleProtocol(Protocol):
    NVMLError_NotSupported: type[Exception]
    NVML_ERROR_NOT_SUPPORTED: int
    nvmlDeviceGetCount: Callable[[], int]
    nvmlDeviceGetHandleByIndex: Callable[[int], NvmlDeviceHandle]
    nvmlDeviceGetUUID: Callable[[NvmlDeviceHandle], str | bytes]
    nvmlDeviceGetPciInfo: Callable[[NvmlDeviceHandle], NvmlPciInfoProtocol]


@dataclass(frozen=True, slots=True)
class NvmlControlObservation:
    value: int | None
    mode: int | None
    user_meaning_verified: bool
    original_restorable: bool
    conversion_failure: StateError | None


@runtime_checkable
class NvmlFanQueryProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlDeviceGetNumFans: Callable[[NvmlDeviceHandle], int]
    nvmlDeviceGetMinMaxFanSpeed: Callable[[NvmlDeviceHandle], list[int]]
    nvmlDeviceGetFanControlPolicy_v2: Callable[[NvmlDeviceHandle, int], int]
    nvmlDeviceGetTargetFanSpeed: Callable[[NvmlDeviceHandle, int], int]


@runtime_checkable
class NvmlControlModuleProtocol(NvmlIdentityModuleProtocol, NvmlFanQueryProtocol, Protocol):
    nvmlDeviceGetPersistenceMode: Callable[[NvmlDeviceHandle], int]
    nvmlDeviceSetPersistenceMode: Callable[[NvmlDeviceHandle, int], None]
    nvmlDeviceGetPowerManagementLimit: Callable[[NvmlDeviceHandle], int]
    nvmlDeviceGetPowerManagementLimitConstraints: Callable[[NvmlDeviceHandle], list[int]]
    nvmlDeviceGetPowerManagementDefaultLimit: Callable[[NvmlDeviceHandle], int]
    nvmlDeviceSetPowerManagementLimit: Callable[[NvmlDeviceHandle, int], None]
    nvmlDeviceSetFanSpeed_v2: Callable[[NvmlDeviceHandle, int, int], int]
    nvmlDeviceSetDefaultFanSpeed_v2: Callable[[NvmlDeviceHandle, int], int]
    nvmlDeviceGetMinMaxClockOfPState: Callable[[NvmlDeviceHandle, int, int], tuple[int, int]]
    nvmlDeviceGetGpcClkVfOffset: Callable[[NvmlDeviceHandle], int]
    nvmlDeviceGetGpcClkMinMaxVfOffset: Callable[[NvmlDeviceHandle], tuple[int, int]]
    nvmlDeviceGetMemClkVfOffset: Callable[[NvmlDeviceHandle], int]
    nvmlDeviceGetMemClkMinMaxVfOffset: Callable[[NvmlDeviceHandle], tuple[int, int]]
    nvmlDeviceSetGpcClkVfOffset: Callable[[NvmlDeviceHandle, int], int]
    nvmlDeviceSetMemClkVfOffset: Callable[[NvmlDeviceHandle, int], int]


@runtime_checkable
class NvmlDeviceGetPowerManagementLimitProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, /) -> int: ...


@runtime_checkable
class NvmlApplicationClockModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlDeviceGetApplicationsClock: Callable[[NvmlDeviceHandle, int], int]
    nvmlDeviceGetSupportedMemoryClocks: Callable[[NvmlDeviceHandle], list[int]]
    nvmlDeviceGetSupportedGraphicsClocks: Callable[[NvmlDeviceHandle, int], list[int]]
    nvmlDeviceSetApplicationsClocks: Callable[[NvmlDeviceHandle, int, int], None]


@runtime_checkable
class NvmlApplicationClockDefaultModuleProtocol(Protocol):
    nvmlDeviceGetDefaultApplicationsClock: Callable[[NvmlDeviceHandle, int], int]


class NvmlClockOffsetPointerProtocol(Protocol):
    contents: NvmlClockOffset


class NvmlClockOffsetFunctionProtocol(Protocol):
    def __call__(
        self, handle: NvmlDeviceHandle, info: NvmlClockOffsetPointerProtocol, /
    ) -> int: ...


@runtime_checkable
class NvmlNativeLibraryModuleProtocol(Protocol):
    nvmlLib: ctypes.CDLL | None
    NVMLError: type[Exception]


class NvmlNativeFunctionResolverProtocol(Protocol):
    @overload
    def __call__(self, name: NvmlClockOffsetSymbol, /) -> NvmlClockOffsetFunctionProtocol: ...

    @overload
    def __call__(
        self, name: Literal["nvmlDeviceSetPowerManagementLimit", "nvmlDeviceSetPersistenceMode"], /
    ) -> Callable[[NvmlDeviceHandle, ctypes.c_uint], int]: ...

    @overload
    def __call__(
        self, name: Literal["nvmlDeviceSetGpcClkVfOffset", "nvmlDeviceSetMemClkVfOffset"], /
    ) -> Callable[[NvmlDeviceHandle, ctypes.c_int32], int]: ...

    @overload
    def __call__(
        self, name: Literal["nvmlDeviceSetApplicationsClocks"], /
    ) -> Callable[[NvmlDeviceHandle, ctypes.c_uint, ctypes.c_uint], int]: ...

    @overload
    def __call__(
        self, name: Literal["nvmlDeviceSetFanSpeed_v2"], /
    ) -> Callable[[NvmlDeviceHandle, int, int], int]: ...

    @overload
    def __call__(
        self, name: Literal["nvmlDeviceSetDefaultFanSpeed_v2"], /
    ) -> Callable[[NvmlDeviceHandle, int], int]: ...


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
class NvApiRuntimeProtocol(Protocol):
    def get_driver_version(self) -> tuple[int, str]: ...


class NvApiFactoryProtocol(Protocol):
    def __call__(self) -> NvApiRuntimeProtocol: ...


class NvidiaSettingsCaptureProtocol(Protocol):
    def __call__(
        self, argv: Sequence[str], *, timeout: int, env: Mapping[str, str] | None
    ) -> CommandResult: ...


@runtime_checkable
class NvApiNativeLibraryProtocol(Protocol):
    nvapi_QueryInterface: Callable[[int], int | None]


@runtime_checkable
class NvApiNativeModuleProtocol(Protocol):
    NvAPI: NvApiFactoryProtocol
    nvapi: NvApiNativeLibraryProtocol
    NvError: type[Exception]


class NvApiFanControlPointerProtocol(Protocol):
    contents: NvApiFanControl


class NvApiFanStatusPointerProtocol(Protocol):
    contents: NvApiFanStatus


class NvApiPstatesPointerProtocol(Protocol):
    contents: NvApiPstates


class NvApiPowerInfoPointerProtocol(Protocol):
    contents: NvApiPowerInfo


class NvApiPowerStatusPointerProtocol(Protocol):
    contents: NvApiPowerStatus


class NvApiUintPointerProtocol(Protocol):
    contents: ctypes.c_uint32


class NvApiFanControlFunctionProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, info: NvApiFanControlPointerProtocol, /) -> int: ...


class NvApiFanStatusFunctionProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, info: NvApiFanStatusPointerProtocol, /) -> int: ...


class NvApiPstatesFunctionProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, info: NvApiPstatesPointerProtocol, /) -> int: ...


class NvApiPowerInfoFunctionProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, info: NvApiPowerInfoPointerProtocol, /) -> int: ...


class NvApiPowerStatusFunctionProtocol(Protocol):
    def __call__(
        self, handle: ctypes.c_void_p, info: NvApiPowerStatusPointerProtocol, /
    ) -> int: ...


class NvApiEnumPhysicalGpusFunctionProtocol(Protocol):
    def __call__(
        self, handles: ctypes.Array[ctypes.c_void_p], count: NvApiUintPointerProtocol, /
    ) -> int: ...


class NvApiBusFunctionProtocol(Protocol):
    def __call__(self, handle: ctypes.c_void_p, value: NvApiUintPointerProtocol, /) -> int: ...

"""SoAI - NVIDIA NVML modern clock-offset reader [backend/hardware/vendors/nvidia/nvml_modern_clock_offsets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING, Literal, overload

from core.errors.exception_logging import log_exception
from core.imports.availability import module_available
from hardware.vendors.nvidia.internal_protocols import (
    NvmlNativeLibraryModuleProtocol,
)
from hardware.vendors.nvidia.nvml_clock_offset_abi import (
    NvmlClockOffsetError,
    read_clock_offset,
    set_clock_offset,
)
from hardware.vendors.nvidia.nvml_clock_offset_structure import NvmlClockOffset

if TYPE_CHECKING:
    from collections.abc import Callable

    from core.logging.protocols import TraceLogger
    from hardware.vendors.nvidia.internal_protocols import (
        NvmlClockOffsetFunctionProtocol,
        NvmlClockOffsetSymbol,
        NvmlDeviceHandle,
        NvmlNativeFunctionResolverProtocol,
        NvmlNativeFunctionSymbol,
    )

__all__ = ("read_modern_clock_offset", "set_modern_clock_offset")

OPERATION_READ_MODERN_CLOCK_OFFSET = (
    "hardware.vendors.nvidia.nvml_modern_clock_offsets.read_modern_clock_offset"
)

pynvml_module = None
native_function_resolver: NvmlNativeFunctionResolverProtocol | None = None
if module_available("pynvml"):
    import pynvml

    pynvml_module = pynvml


@overload
def _resolve_sdk_native_function(
    name: NvmlClockOffsetSymbol, /
) -> NvmlClockOffsetFunctionProtocol: ...


@overload
def _resolve_sdk_native_function(
    name: Literal["nvmlDeviceSetPowerManagementLimit", "nvmlDeviceSetPersistenceMode"], /
) -> Callable[[NvmlDeviceHandle, ctypes.c_uint], int]: ...


@overload
def _resolve_sdk_native_function(
    name: Literal["nvmlDeviceSetGpcClkVfOffset", "nvmlDeviceSetMemClkVfOffset"], /
) -> Callable[[NvmlDeviceHandle, ctypes.c_int32], int]: ...


@overload
def _resolve_sdk_native_function(
    name: Literal["nvmlDeviceSetApplicationsClocks"], /
) -> Callable[[NvmlDeviceHandle, ctypes.c_uint, ctypes.c_uint], int]: ...


@overload
def _resolve_sdk_native_function(
    name: Literal["nvmlDeviceSetFanSpeed_v2"], /
) -> Callable[[NvmlDeviceHandle, int, int], int]: ...


@overload
def _resolve_sdk_native_function(
    name: Literal["nvmlDeviceSetDefaultFanSpeed_v2"], /
) -> Callable[[NvmlDeviceHandle, int], int]: ...


def _resolve_sdk_native_function(
    name: NvmlNativeFunctionSymbol, /
) -> (
    NvmlClockOffsetFunctionProtocol
    | Callable[[NvmlDeviceHandle, ctypes.c_uint], int]
    | Callable[[NvmlDeviceHandle, ctypes.c_int32], int]
    | Callable[[NvmlDeviceHandle, ctypes.c_uint, ctypes.c_uint], int]
    | Callable[[NvmlDeviceHandle, int, int], int]
    | Callable[[NvmlDeviceHandle, int], int]
):
    active_module = pynvml_module
    if not isinstance(active_module, NvmlNativeLibraryModuleProtocol):
        raise _resolver_acquisition_failure()
    library = active_module.nvmlLib
    if library is None:
        raise active_module.NVMLError(9)
    if not isinstance(library, ctypes.CDLL):
        raise _resolver_acquisition_failure()
    try:
        if name in ("nvmlDeviceGetClockOffsets", "nvmlDeviceSetClockOffsets"):
            return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(NvmlClockOffset))(
                (name, library)
            )
        if name in ("nvmlDeviceSetPowerManagementLimit", "nvmlDeviceSetPersistenceMode"):
            return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint)((name, library))
        if name in ("nvmlDeviceSetGpcClkVfOffset", "nvmlDeviceSetMemClkVfOffset"):
            return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_int32)((name, library))
        if name == "nvmlDeviceSetApplicationsClocks":
            return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint)(
                ("nvmlDeviceSetApplicationsClocks", library)
            )
        if name == "nvmlDeviceSetFanSpeed_v2":
            return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint)(
                ("nvmlDeviceSetFanSpeed_v2", library)
            )
        if name == "nvmlDeviceSetDefaultFanSpeed_v2":
            return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_uint)(
                ("nvmlDeviceSetDefaultFanSpeed_v2", library)
            )
    except AttributeError as exception:
        raise active_module.NVMLError(13) from exception
    raise _resolver_acquisition_failure()


if pynvml_module is not None:
    native_function_resolver = _resolve_sdk_native_function


def read_modern_clock_offset(
    *,
    handle: NvmlDeviceHandle,
    clock_type: int,
    pstate: int,
    logger: TraceLogger,
    operation: str,
) -> tuple[int, int, int] | NvmlClockOffsetError | None:
    active_module = pynvml_module
    resolver = native_function_resolver
    if active_module is None:
        return None
    try:
        if resolver is None:
            raise _resolver_acquisition_failure()
        return read_clock_offset(
            handle=handle,
            clock_type=clock_type,
            pstate=pstate,
            resolve_function=resolver,
            native_error=active_module.NVMLError,
        )
    except NvmlClockOffsetError as exception:
        if not exception.native_invoked and exception.native_status == 13:
            return None
        log_exception(
            logger,
            exception,
            message="NVML modern clock-offset query failed (non-critical).",
            operation=OPERATION_READ_MODERN_CLOCK_OFFSET,
            details={
                "nvml_operation": operation,
                "native_status": exception.native_status,
                "native_invoked": exception.native_invoked,
                "actuator_invoked": exception.actuator_invoked,
            },
            level="trace",
        )
        return exception


def set_modern_clock_offset(
    *,
    handle: NvmlDeviceHandle,
    clock_type: int | None,
    pstate: int | None,
    offset_mhz: int,
) -> bool:
    active_module = pynvml_module
    resolver = native_function_resolver
    if active_module is None or clock_type is None or pstate is None:
        return False
    if resolver is None:
        raise _resolver_acquisition_failure()
    try:
        set_clock_offset(
            handle=handle,
            clock_type=clock_type,
            pstate=pstate,
            offset_mhz=offset_mhz,
            resolve_function=resolver,
            native_error=active_module.NVMLError,
        )
    except NvmlClockOffsetError as exception:
        if not exception.native_invoked and exception.native_status == 13:
            return False
        raise
    return True


def _resolver_acquisition_failure() -> NvmlClockOffsetError:
    return NvmlClockOffsetError(
        "NVML SDK native function resolver could not be acquired.",
        details={"native_invoked": False, "actuator_invoked": False, "native_status": None},
    )

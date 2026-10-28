"""SoAI - Status-bearing NVML clock offset ABI [backend/hardware/vendors/nvidia/nvml_clock_offset_abi.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from hardware.vendors.nvidia.internal_protocols import (
    NvmlClockOffsetFunctionProtocol,
    NvmlErrorValueProtocol,
    NvmlNativeHandleProtocol,
)
from hardware.vendors.nvidia.nvml_clock_offset_structure import NvmlClockOffset

if TYPE_CHECKING:
    from hardware.vendors.nvidia.internal_protocols import (
        NvmlClockOffsetResolver,
        NvmlClockOffsetSymbol,
        NvmlDeviceHandle,
    )


__all__ = (
    "NvmlClockOffsetError",
    "read_clock_offset",
    "resolve_clock_offset_function",
    "set_clock_offset",
)

_CLOCK_OFFSET_VERSION = 0x1000018


class NvmlClockOffsetError(StateError):
    @property
    def actuator_invoked(self) -> bool:
        value = self.details.get("actuator_invoked") if self.details is not None else None
        if not isinstance(value, bool):
            raise StateError("NVML clock-offset failure has no explicit invocation evidence.")
        return value

    @property
    def native_invoked(self) -> bool:
        value = self.details.get("native_invoked") if self.details is not None else None
        if not isinstance(value, bool):
            raise StateError(
                "NVML clock-offset failure has no explicit native invocation evidence."
            )
        return value

    @property
    def native_status(self) -> int | None:
        value = self.details.get("native_status") if self.details is not None else None
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise StateError("NVML clock-offset failure contains an invalid native status.")
        return value


def _native_status(exception: Exception) -> int | None:
    if (
        isinstance(exception, NvmlErrorValueProtocol)
        and isinstance(exception.value, int)
        and not isinstance(exception.value, bool)
    ):
        return exception.value
    return None


def _initialize_relation(handle: NvmlDeviceHandle, clock_type: int, pstate: int) -> NvmlClockOffset:
    if handle is None or not handle:
        raise ValidationError("NVML clock-offset operation requires a nonnull current handle.")
    if not isinstance(handle, ctypes.c_void_p | NvmlNativeHandleProtocol):
        raise ValidationError("NVML clock-offset operation requires an actual native handle.")
    if (
        not isinstance(clock_type, int)
        or isinstance(clock_type, bool)
        or clock_type not in (0, 1, 2, 3)
    ):
        raise ValidationError("NVML clock-offset domain is outside the declared native ABI.")
    if not isinstance(pstate, int) or isinstance(pstate, bool) or not 0 <= pstate <= 15:
        raise ValidationError("NVML clock-offset P-state is outside the declared native ABI.")
    info = NvmlClockOffset()
    info.version = _CLOCK_OFFSET_VERSION
    info.type = clock_type
    info.pstate = pstate
    return info


def resolve_clock_offset_function(
    name: NvmlClockOffsetSymbol,
    resolve_function: NvmlClockOffsetResolver,
    native_error: type[Exception],
) -> NvmlClockOffsetFunctionProtocol:
    if name not in ("nvmlDeviceGetClockOffsets", "nvmlDeviceSetClockOffsets"):
        raise ValidationError("NVML clock-offset native symbol is outside the declared ABI.")
    try:
        function = resolve_function(name)
    except (native_error, ctypes.ArgumentError) as exception:
        raise NvmlClockOffsetError(
            "NVML clock-offset native function acquisition failed.",
            details={
                "actuator_invoked": False,
                "native_invoked": False,
                "native_status": _native_status(exception),
            },
            cause=exception,
        ) from exception
    if not callable(function):
        raise NvmlClockOffsetError(
            "NVML clock-offset native function acquisition returned a malformed facility.",
            details={"actuator_invoked": False, "native_invoked": False, "native_status": None},
        )
    return function


def _invoke(
    function: NvmlClockOffsetFunctionProtocol,
    handle: NvmlDeviceHandle,
    info: NvmlClockOffset,
    *,
    native_error: type[Exception],
    actuator_invoked: bool,
) -> None:
    try:
        status = function(handle, ctypes.pointer(info))
    except (native_error, ctypes.ArgumentError) as exception:
        raise NvmlClockOffsetError(
            "NVML clock-offset native invocation failed.",
            details={
                "actuator_invoked": actuator_invoked,
                "native_invoked": True,
                "native_status": _native_status(exception),
            },
            cause=exception,
        ) from exception
    if not isinstance(status, int) or isinstance(status, bool) or status != 0:
        raise NvmlClockOffsetError(
            "NVML clock-offset native invocation did not return success.",
            details={
                "actuator_invoked": actuator_invoked,
                "native_invoked": True,
                "native_status": (
                    status if isinstance(status, int) and not isinstance(status, bool) else None
                ),
            },
        )


def read_clock_offset(
    *,
    handle: NvmlDeviceHandle,
    clock_type: int,
    pstate: int,
    resolve_function: NvmlClockOffsetResolver,
    native_error: type[Exception],
) -> tuple[int, int, int]:
    info = _initialize_relation(handle, clock_type, pstate)
    function = resolve_clock_offset_function(
        "nvmlDeviceGetClockOffsets", resolve_function, native_error
    )
    _invoke(function, handle, info, native_error=native_error, actuator_invoked=False)
    relation_valid = (
        info.version == _CLOCK_OFFSET_VERSION and info.type == clock_type and info.pstate == pstate
    )
    if not relation_valid or not (
        info.min_clock_offset_mhz <= info.clock_offset_mhz <= info.max_clock_offset_mhz
    ):
        raise NvmlClockOffsetError(
            "NVML clock-offset query returned an invalid native relation or range.",
            details={"actuator_invoked": False, "native_invoked": True, "native_status": 0},
        )
    return info.clock_offset_mhz, info.min_clock_offset_mhz, info.max_clock_offset_mhz


def set_clock_offset(
    *,
    handle: NvmlDeviceHandle,
    clock_type: int,
    pstate: int,
    offset_mhz: int,
    resolve_function: NvmlClockOffsetResolver,
    native_error: type[Exception],
) -> None:
    info = _initialize_relation(handle, clock_type, pstate)
    if (
        not isinstance(offset_mhz, int)
        or isinstance(offset_mhz, bool)
        or not -(2**31) <= offset_mhz < 2**31
    ):
        raise ValidationError("NVML clock offset requires a signed native 32-bit MHz value.")
    info.clock_offset_mhz = offset_mhz
    function = resolve_clock_offset_function(
        "nvmlDeviceSetClockOffsets", resolve_function, native_error
    )
    _invoke(function, handle, info, native_error=native_error, actuator_invoked=True)

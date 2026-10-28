"""SoAI - Exact native NvAPI function acquisition [backend/hardware/vendors/nvidia/nvapi_function_acquisition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING, Literal, overload

from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.validation.strict_integer import is_strict_int
from hardware.vendors.nvidia.internal_protocols import (
    NvApiBusFunctionProtocol,
    NvApiEnumPhysicalGpusFunctionProtocol,
    NvApiFanControlFunctionProtocol,
    NvApiFanStatusFunctionProtocol,
    NvApiPowerInfoFunctionProtocol,
    NvApiPowerStatusFunctionProtocol,
    NvApiPstatesFunctionProtocol,
)
from hardware.vendors.nvidia.nvapi_fan_types import NvApiFanControl, NvApiFanStatus
from hardware.vendors.nvidia.nvapi_native_types import NvApiPstates
from hardware.vendors.nvidia.nvapi_power_types import NvApiPowerInfo, NvApiPowerStatus

if TYPE_CHECKING:
    from collections.abc import Callable

    type NvApiFunctionSymbol = Literal[
        "NvAPI_EnumPhysicalGPUs",
        "NvAPI_GPU_GetBusId",
        "NvAPI_GPU_GetBusSlotId",
        "NvAPI_GPU_ClientFanCoolersGetControl",
        "NvAPI_GPU_ClientFanCoolersSetControl",
        "NvAPI_GPU_ClientFanCoolersGetStatus",
        "NvAPI_GPU_GetPstates20",
        "NvAPI_GPU_SetPstates20",
        "NvAPI_GPU_ClientPowerPoliciesGetInfo",
        "NvAPI_GPU_ClientPowerPoliciesGetStatus",
        "NvAPI_GPU_ClientPowerPoliciesSetStatus",
    ]


__all__ = (
    "resolve_nvapi_function",
    "require_nvapi_native_success",
)


@overload
def resolve_nvapi_function(
    symbol: Literal["NvAPI_EnumPhysicalGPUs"], *, query_interface: Callable[[int], int | None]
) -> NvApiEnumPhysicalGpusFunctionProtocol | None: ...


@overload
def resolve_nvapi_function(
    symbol: Literal["NvAPI_GPU_GetBusId", "NvAPI_GPU_GetBusSlotId"],
    *,
    query_interface: Callable[[int], int | None],
) -> NvApiBusFunctionProtocol | None: ...


@overload
def resolve_nvapi_function(
    symbol: Literal["NvAPI_GPU_ClientFanCoolersGetControl", "NvAPI_GPU_ClientFanCoolersSetControl"],
    *,
    query_interface: Callable[[int], int | None],
) -> NvApiFanControlFunctionProtocol | None: ...


@overload
def resolve_nvapi_function(
    symbol: Literal["NvAPI_GPU_ClientFanCoolersGetStatus"],
    *,
    query_interface: Callable[[int], int | None],
) -> NvApiFanStatusFunctionProtocol | None: ...


@overload
def resolve_nvapi_function(
    symbol: Literal["NvAPI_GPU_GetPstates20", "NvAPI_GPU_SetPstates20"],
    *,
    query_interface: Callable[[int], int | None],
) -> NvApiPstatesFunctionProtocol | None: ...


@overload
def resolve_nvapi_function(
    symbol: Literal["NvAPI_GPU_ClientPowerPoliciesGetInfo"],
    *,
    query_interface: Callable[[int], int | None],
) -> NvApiPowerInfoFunctionProtocol | None: ...


@overload
def resolve_nvapi_function(
    symbol: Literal[
        "NvAPI_GPU_ClientPowerPoliciesGetStatus", "NvAPI_GPU_ClientPowerPoliciesSetStatus"
    ],
    *,
    query_interface: Callable[[int], int | None],
) -> NvApiPowerStatusFunctionProtocol | None: ...


def resolve_nvapi_function(
    symbol: NvApiFunctionSymbol,
    *,
    query_interface: Callable[[int], int | None],
) -> (
    NvApiEnumPhysicalGpusFunctionProtocol
    | NvApiBusFunctionProtocol
    | NvApiFanControlFunctionProtocol
    | NvApiFanStatusFunctionProtocol
    | NvApiPstatesFunctionProtocol
    | NvApiPowerInfoFunctionProtocol
    | NvApiPowerStatusFunctionProtocol
    | None
):
    interface_ids = {
        "NvAPI_EnumPhysicalGPUs": 0xE5AC921F,
        "NvAPI_GPU_GetBusId": 0x1BE0B8E5,
        "NvAPI_GPU_GetBusSlotId": 0x2A0A350F,
        "NvAPI_GPU_ClientFanCoolersGetControl": 0x814B209F,
        "NvAPI_GPU_ClientFanCoolersSetControl": 0xA58971A5,
        "NvAPI_GPU_ClientFanCoolersGetStatus": 0x35AED5E8,
        "NvAPI_GPU_GetPstates20": 0x6FF81213,
        "NvAPI_GPU_SetPstates20": 0x0F4DAE6B,
        "NvAPI_GPU_ClientPowerPoliciesGetInfo": 0x34206D86,
        "NvAPI_GPU_ClientPowerPoliciesGetStatus": 0x70916171,
        "NvAPI_GPU_ClientPowerPoliciesSetStatus": 0xAD95F5ED,
    }

    if not isinstance(symbol, str) or symbol not in interface_ids or not callable(query_interface):
        raise ValidationError(
            "NvAPI acquisition requires an exact declared native symbol and query."
        )
    acquisition_failures: tuple[type[Exception], ...] = (
        ctypes.ArgumentError,
        *HANDLED_RUNTIME_EXCEPTIONS,
    )
    try:
        address = query_interface(interface_ids[symbol])
    except acquisition_failures as exception:
        raise StateError(
            "NvAPI native function acquisition failed before invocation.",
            details={"symbol": symbol, "actuator_invoked": False, "native_invoked": False},
            cause=exception,
        ) from exception
    if address is None:
        return None
    if (
        not is_strict_int(address)
        or address < 0
        or address >= 1 << (ctypes.sizeof(ctypes.c_void_p) * 8)
    ):
        raise ValidationError("NvAPI function address is invalid.")
    if address == 0:
        return None
    if symbol == "NvAPI_EnumPhysicalGPUs":
        return ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)
        )(address)
    if symbol in ("NvAPI_GPU_GetBusId", "NvAPI_GPU_GetBusSlotId"):
        return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))(
            address
        )
    if symbol in ("NvAPI_GPU_ClientFanCoolersGetControl", "NvAPI_GPU_ClientFanCoolersSetControl"):
        return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(NvApiFanControl))(
            address
        )
    if symbol == "NvAPI_GPU_ClientFanCoolersGetStatus":
        return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(NvApiFanStatus))(
            address
        )
    if symbol in ("NvAPI_GPU_GetPstates20", "NvAPI_GPU_SetPstates20"):
        return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(NvApiPstates))(
            address
        )
    if symbol == "NvAPI_GPU_ClientPowerPoliciesGetInfo":
        return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(NvApiPowerInfo))(
            address
        )
    return ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(NvApiPowerStatus))(
        address
    )


def require_nvapi_native_success(status: int, *, actuator_invoked: bool) -> None:
    if not is_strict_int(status):
        raise ValidationError("NvAPI native operation status is invalid.")
    if status != 0:
        raise StateError(
            "NvAPI native operation failed.",
            details={"native_status": status, "actuator_invoked": actuator_invoked},
        )

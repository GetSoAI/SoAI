"""SoAI - Windows adapter LUID to PCI address bridge [backend/core/hardware/windows_adapter_address.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import struct

from core.platform.os import is_windows
from core.system.windows_ctypes import load_windows_library

__all__ = (
    "load_windows_adapter_library",
    "read_windows_adapter_address",
)

KMTQAITYPE_ADAPTERADDRESS = 6


class WindowsLuid(ctypes.Structure):
    _fields_ = (("low_part", ctypes.c_uint32), ("high_part", ctypes.c_int32))


class OpenAdapterFromLuid(ctypes.Structure):
    _fields_ = (("adapter_luid", WindowsLuid), ("adapter", ctypes.c_uint32))


class QueryAdapterInfo(ctypes.Structure):
    _fields_ = (
        ("adapter", ctypes.c_uint32),
        ("type", ctypes.c_int32),
        ("private_driver_data", ctypes.c_void_p),
        ("private_driver_data_size", ctypes.c_uint32),
    )


class AdapterAddress(ctypes.Structure):
    _fields_ = (
        ("bus_number", ctypes.c_uint32),
        ("device_number", ctypes.c_uint32),
        ("function_number", ctypes.c_uint32),
    )


class CloseAdapter(ctypes.Structure):
    _fields_ = (("adapter", ctypes.c_uint32),)


def load_windows_adapter_library() -> ctypes.CDLL | None:
    return load_windows_library("gdi32") if is_windows() else None


def read_windows_adapter_address(
    library: ctypes.CDLL, device_luid: bytes
) -> tuple[int, int, int] | None:
    library.D3DKMTOpenAdapterFromLuid.argtypes = [ctypes.POINTER(OpenAdapterFromLuid)]
    library.D3DKMTOpenAdapterFromLuid.restype = ctypes.c_int32
    library.D3DKMTQueryAdapterInfo.argtypes = [ctypes.POINTER(QueryAdapterInfo)]
    library.D3DKMTQueryAdapterInfo.restype = ctypes.c_int32
    library.D3DKMTCloseAdapter.argtypes = [ctypes.POINTER(CloseAdapter)]
    library.D3DKMTCloseAdapter.restype = ctypes.c_int32
    low_part, high_part = struct.unpack("<Ii", device_luid)
    request = OpenAdapterFromLuid(adapter_luid=WindowsLuid(low_part=low_part, high_part=high_part))
    if library.D3DKMTOpenAdapterFromLuid(ctypes.byref(request)) != 0 or not request.adapter:
        return None
    try:
        address = AdapterAddress()
        query = QueryAdapterInfo(
            adapter=request.adapter,
            type=KMTQAITYPE_ADAPTERADDRESS,
            private_driver_data=ctypes.addressof(address),
            private_driver_data_size=ctypes.sizeof(address),
        )
        if library.D3DKMTQueryAdapterInfo(ctypes.byref(query)) != 0:
            return None
        return (address.bus_number, address.device_number, address.function_number)
    finally:
        library.D3DKMTCloseAdapter(ctypes.byref(CloseAdapter(adapter=request.adapter)))

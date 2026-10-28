"""SoAI - Fixed Windows x64 ADL Cdecl layouts and trusted library loading [backend/hardware/vendors/amd/adl_abi.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from types import EllipsisType

from _ctypes import FUNCFLAG_CDECL, CFuncPtr

from core.errors.exceptions import StateError, ValidationError
from core.runtime.platform import get_runtime_platform
from core.system.windows_ctypes import load_kernel32

__all__ = (
    "AdlAdapterInfo",
    "AdlInitialSetting",
    "AdlSingleSetting",
    "AdlAllocatorCallback",
    "validate_adl_layouts",
    "load_adl_library",
    "bind_adl_functions",
    "AdlAdapterObservation",
    "AdlFeatureObservation",
    "AdlControlObservation",
)


class AdlAdapterInfo(ctypes.Structure):
    size: int
    udid: bytes
    adapter_name: bytes
    display_name: bytes
    driver_path: bytes
    driver_path_ext: bytes
    os_display_index: int

    _fields_ = (
        ("size", ctypes.c_int32),
        ("adapter_index", ctypes.c_int32),
        ("udid", ctypes.c_char * 256),
        ("bus", ctypes.c_int32),
        ("device", ctypes.c_int32),
        ("function", ctypes.c_int32),
        ("vendor", ctypes.c_int32),
        ("adapter_name", ctypes.c_char * 256),
        ("display_name", ctypes.c_char * 256),
        ("present", ctypes.c_int32),
        ("exists", ctypes.c_int32),
        ("driver_path", ctypes.c_char * 256),
        ("driver_path_ext", ctypes.c_char * 256),
        ("pnp_string", ctypes.c_char * 256),
        ("os_display_index", ctypes.c_int32),
    )

    def __init__(
        self,
        size: int | EllipsisType = ...,
        adapter_index: int | EllipsisType = ...,
        udid: bytes | EllipsisType = ...,
        bus: int | EllipsisType = ...,
        device: int | EllipsisType = ...,
        function: int | EllipsisType = ...,
        vendor: int | EllipsisType = ...,
        adapter_name: bytes | EllipsisType = ...,
        display_name: bytes | EllipsisType = ...,
        present: int | EllipsisType = ...,
        exists: int | EllipsisType = ...,
        driver_path: bytes | EllipsisType = ...,
        driver_path_ext: bytes | EllipsisType = ...,
        pnp_string: bytes | EllipsisType = ...,
        os_display_index: int | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if size is not ...:
            self.size = size
        if adapter_index is not ...:
            self.adapter_index = adapter_index
        if udid is not ...:
            self.udid = udid
        if bus is not ...:
            self.bus = bus
        if device is not ...:
            self.device = device
        if function is not ...:
            self.function = function
        if vendor is not ...:
            self.vendor = vendor
        if adapter_name is not ...:
            self.adapter_name = adapter_name
        if display_name is not ...:
            self.display_name = display_name
        if present is not ...:
            self.present = present
        if exists is not ...:
            self.exists = exists
        if driver_path is not ...:
            self.driver_path = driver_path
        if driver_path_ext is not ...:
            self.driver_path_ext = driver_path_ext
        if pnp_string is not ...:
            self.pnp_string = pnp_string
        if os_display_index is not ...:
            self.os_display_index = os_display_index


class AdlInitialSetting(ctypes.Structure):
    feature_bit: int
    minimum: int
    maximum: int
    default: int

    _fields_ = (
        ("feature_bit", ctypes.c_int32),
        ("minimum", ctypes.c_int32),
        ("maximum", ctypes.c_int32),
        ("default", ctypes.c_int32),
    )

    def __init__(
        self,
        feature_bit: int | EllipsisType = ...,
        minimum: int | EllipsisType = ...,
        maximum: int | EllipsisType = ...,
        default: int | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if feature_bit is not ...:
            self.feature_bit = feature_bit
        if minimum is not ...:
            self.minimum = minimum
        if maximum is not ...:
            self.maximum = maximum
        if default is not ...:
            self.default = default


class AdlSingleSetting(ctypes.Structure):
    value: int
    requested: int
    reset: int

    _fields_ = (
        ("value", ctypes.c_int32),
        ("requested", ctypes.c_int32),
        ("reset", ctypes.c_int32),
    )

    def __init__(
        self,
        value: int | EllipsisType = ...,
        requested: int | EllipsisType = ...,
        reset: int | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if value is not ...:
            self.value = value
        if requested is not ...:
            self.requested = requested
        if reset is not ...:
            self.reset = reset


class AdlAllocatorCallback(CFuncPtr):
    _argtypes_ = (ctypes.c_int32,)
    _restype_ = ctypes.c_void_p
    _flags_ = FUNCFLAG_CDECL


def validate_adl_layouts() -> None:
    observed = (
        ctypes.sizeof(AdlAdapterInfo),
        ctypes.sizeof(AdlInitialSetting),
        ctypes.sizeof(AdlSingleSetting),
        ctypes.sizeof(ctypes.c_int32),
    )
    if observed != (1572, 16, 12, 4):
        raise ValidationError("ADL native structure layout is incompatible.")
    adapter = AdlAdapterInfo(
        adapter_index=1,
        bus=2,
        device=3,
        function=4,
        vendor=5,
        present=6,
        exists=7,
        pnp_string=b"ADL-layout",
    )
    expected = bytearray(1572)
    for offset, value in ((4, 1), (264, 2), (268, 3), (272, 4), (276, 5), (792, 6), (796, 7)):
        expected[offset : offset + 4] = value.to_bytes(4, "little", signed=True)
    expected[1312:1322] = b"ADL-layout"
    if bytes(adapter) != expected:
        raise ValidationError("ADL native structure layout is incompatible.")


def load_adl_library() -> ctypes.CDLL:
    platform = get_runtime_platform()
    if not platform.is_windows or platform.architecture_id != "x64":
        raise StateError("ADL controls require the supported Windows x64 architecture.")
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise StateError("ADL controls require the supported 64-bit process ABI.")
    validate_adl_layouts()
    kernel = load_kernel32()
    kernel.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetSystemDirectoryW.restype = ctypes.c_uint32
    directory = ctypes.create_unicode_buffer(32768)
    length = kernel.GetSystemDirectoryW(directory, len(directory))
    if length == 0 or length >= len(directory) or not os.path.isabs(directory.value):
        raise StateError("ADL trusted native library directory is unavailable.")
    try:
        library = ctypes.CDLL(os.path.join(directory.value, "atiadlxx.dll"), winmode=0x00000900)
    except OSError as exception:
        raise StateError("ADL native library is unavailable.", cause=exception) from exception
    bind_adl_functions(library)
    return library


def bind_adl_functions(library: ctypes.CDLL) -> None:
    validate_adl_layouts()
    try:
        library.ADL2_Main_Control_Create.argtypes = [
            AdlAllocatorCallback,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        library.ADL2_Main_Control_Create.restype = ctypes.c_int32
        library.ADL2_Main_Control_Destroy.argtypes = [ctypes.c_void_p]
        library.ADL2_Main_Control_Destroy.restype = ctypes.c_int32
        library.ADL2_Adapter_NumberOfAdapters_Get.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int32),
        ]
        library.ADL2_Adapter_NumberOfAdapters_Get.restype = ctypes.c_int32
        library.ADL2_Adapter_AdapterInfo_Get.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(AdlAdapterInfo),
            ctypes.c_int32,
        ]
        library.ADL2_Adapter_AdapterInfo_Get.restype = ctypes.c_int32
        library.ADL2_Overdrive_Caps.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int32),
            ctypes.POINTER(ctypes.c_int32),
            ctypes.POINTER(ctypes.c_int32),
        ]
        library.ADL2_Overdrive_Caps.restype = ctypes.c_int32
        library.ADL2_Overdrive8_Init_SettingX2_Get.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int32),
            ctypes.POINTER(ctypes.c_int32),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        library.ADL2_Overdrive8_Init_SettingX2_Get.restype = ctypes.c_int32
        library.ADL2_Overdrive8_Current_SettingX2_Get.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int32),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        library.ADL2_Overdrive8_Current_SettingX2_Get.restype = ctypes.c_int32
        library.ADL2_Overdrive8_Setting_Set.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        library.ADL2_Overdrive8_Setting_Set.restype = ctypes.c_int32
    except AttributeError as exception:
        raise StateError(
            "ADL required native export is unavailable.", cause=exception
        ) from exception


@dataclass(frozen=True, slots=True)
class AdlAdapterObservation:
    adapter_index: int
    bus: int
    device: int
    function: int
    vendor: int
    present: bool
    exists: bool
    udid: str
    pnp_instance: str


@dataclass(frozen=True, slots=True)
class AdlFeatureObservation:
    feature_bit: int
    minimum: int
    maximum: int
    default: int


@dataclass(frozen=True, slots=True)
class AdlControlObservation:
    adapter: AdlAdapterObservation
    capabilities: int
    features: tuple[AdlFeatureObservation, ...]
    current: tuple[int, ...]

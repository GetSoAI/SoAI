"""SoAI - Native Windows display device inventory [backend/core/hardware/windows_pnp_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from uuid import UUID

from core.errors.exceptions import ValidationError
from core.system.windows_ctypes import last_windows_error, load_windows_library
from core.types.json import JSONDict

__all__ = ("read_windows_display_devices",)

DISPLAY_CLASS = "4d36e968-e325-11ce-bfc1-08002be10318"
DEVICE_PROPERTIES = "a45c254e-df1c-4efd-8020-67d146a850e0"
DRIVER_PROPERTIES = "a8b865dd-2e3d-4094-ad97-e593a70c75d6"
DEVICE_STATUS_PROPERTIES = "4340a6c5-93fa-4706-972c-7b648008a5a7"
DIGCF_PRESENT = 2
ERROR_NO_MORE_ITEMS = 259
ERROR_NOT_FOUND = 1168
ERROR_INSUFFICIENT_BUFFER = 122
MAX_PROPERTY_BYTES = 65536
MAX_DISPLAY_DEVICES = 256


class WindowsGuid(ctypes.Structure):
    _fields_ = (
        ("data1", ctypes.c_uint32),
        ("data2", ctypes.c_uint16),
        ("data3", ctypes.c_uint16),
        ("data4", ctypes.c_ubyte * 8),
    )


class WindowsDeviceInfo(ctypes.Structure):
    _fields_ = (
        ("size", ctypes.c_uint32),
        ("class_guid", WindowsGuid),
        ("instance", ctypes.c_uint32),
        ("reserved", ctypes.c_void_p),
    )


class WindowsDevicePropertyKey(ctypes.Structure):
    _fields_ = (("format", WindowsGuid), ("property_id", ctypes.c_uint32))


def _configure_inventory_library(library: ctypes.CDLL) -> None:
    library.SetupDiGetClassDevsW.argtypes = [
        ctypes.POINTER(WindowsGuid),
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    library.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    library.SetupDiEnumDeviceInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(WindowsDeviceInfo),
    ]
    library.SetupDiEnumDeviceInfo.restype = ctypes.c_int
    library.SetupDiGetDeviceInstanceIdW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(WindowsDeviceInfo),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    library.SetupDiGetDeviceInstanceIdW.restype = ctypes.c_int
    library.SetupDiGetDevicePropertyW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(WindowsDeviceInfo),
        ctypes.POINTER(WindowsDevicePropertyKey),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_uint32,
    ]
    library.SetupDiGetDevicePropertyW.restype = ctypes.c_int
    library.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    library.SetupDiDestroyDeviceInfoList.restype = ctypes.c_int


def _inventory_error(operation: str, error: int) -> OSError:
    if error == 5:
        return PermissionError(f"Windows display inventory denied access: {operation}.")
    return OSError(f"Windows display inventory failed: {operation}; Windows error {error}.")


def _read_property(
    library: ctypes.CDLL,
    handle: int,
    device: WindowsDeviceInfo,
    format_id: str,
    property_id: int,
    expected_type: int,
) -> str | int | None:
    property_key = WindowsDevicePropertyKey(
        WindowsGuid.from_buffer_copy(UUID(format_id).bytes_le), property_id
    )
    property_type = ctypes.c_uint32()
    required = ctypes.c_uint32()
    buffer = ctypes.create_string_buffer(512)
    for _attempt in range(3):
        success = library.SetupDiGetDevicePropertyW(
            handle,
            ctypes.byref(device),
            ctypes.byref(property_key),
            ctypes.byref(property_type),
            buffer,
            len(buffer),
            ctypes.byref(required),
            0,
        )
        if success:
            if property_type.value != expected_type or not 0 < required.value <= len(buffer):
                raise ValidationError("Windows display property has an invalid type or size.")
            value = buffer.raw[: required.value]
            if expected_type == 7:
                if len(value) != 4:
                    raise ValidationError("Windows display integer property has an invalid size.")
                return int.from_bytes(value, "little")
            if len(value) % 2 or not value.endswith(b"\x00\x00"):
                raise ValidationError("Windows display string property is not terminated.")
            text = value[:-2].decode("utf-16-le")
            if "\x00" in text:
                raise ValidationError("Windows display string property contains a null.")
            return text
        error = last_windows_error()
        if error == ERROR_NOT_FOUND:
            return None
        if error != ERROR_INSUFFICIENT_BUFFER:
            raise _inventory_error("SetupDiGetDevicePropertyW", error)
        if not len(buffer) < required.value <= MAX_PROPERTY_BYTES:
            raise ValidationError("Windows display property exceeds its bounded buffer.")
        buffer = ctypes.create_string_buffer(required.value)
    raise OSError("Windows display property changed repeatedly during acquisition.")


def _read_device_identity(library: ctypes.CDLL, handle: int, device: WindowsDeviceInfo) -> str:
    buffer = ctypes.create_unicode_buffer(4096)
    required = ctypes.c_uint32()
    if not library.SetupDiGetDeviceInstanceIdW(
        handle, ctypes.byref(device), buffer, len(buffer), ctypes.byref(required)
    ):
        raise _inventory_error("SetupDiGetDeviceInstanceIdW", last_windows_error())
    identity = buffer.value
    if not identity.strip() or not 1 < required.value <= len(buffer):
        raise ValidationError("Windows display instance identity is invalid.")
    return identity


def _read_display_device(library: ctypes.CDLL, handle: int, device: WindowsDeviceInfo) -> JSONDict:
    identity = _read_device_identity(library, handle, device)
    friendly_name = _read_property(library, handle, device, DEVICE_PROPERTIES, 14, 18)
    description = _read_property(library, handle, device, DEVICE_PROPERTIES, 2, 18)
    problem = _read_property(library, handle, device, DEVICE_STATUS_PROPERTIES, 3, 7)
    if problem is None:
        raise ValidationError("Windows display device problem state is unavailable.")
    return {
        "PNPDeviceID": identity,
        "DeviceID": identity,
        "Name": friendly_name or description,
        "DriverVersion": _read_property(library, handle, device, DRIVER_PROPERTIES, 3, 18),
        "DriverSource": "setupapi.device_driver",
        "AdapterCompatibility": _read_property(library, handle, device, DEVICE_PROPERTIES, 13, 18),
        "PciBusNumber": _read_property(library, handle, device, DEVICE_PROPERTIES, 23, 7),
        "PciAddress": _read_property(library, handle, device, DEVICE_PROPERTIES, 30, 7),
        "ConfigManagerErrorCode": problem,
    }


def read_windows_display_devices() -> list[JSONDict]:
    library = load_windows_library("setupapi", use_last_error=True)
    _configure_inventory_library(library)
    display_class = WindowsGuid.from_buffer_copy(UUID(DISPLAY_CLASS).bytes_le)
    handle = library.SetupDiGetClassDevsW(ctypes.byref(display_class), None, None, DIGCF_PRESENT)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise _inventory_error("SetupDiGetClassDevsW", last_windows_error())
    try:
        records: list[JSONDict] = []
        for index in range(MAX_DISPLAY_DEVICES):
            device = WindowsDeviceInfo(size=ctypes.sizeof(WindowsDeviceInfo))
            if not library.SetupDiEnumDeviceInfo(handle, index, ctypes.byref(device)):
                error = last_windows_error()
                if error == ERROR_NO_MORE_ITEMS:
                    return records
                raise _inventory_error("SetupDiEnumDeviceInfo", error)
            records.append(_read_display_device(library, handle, device))
        raise ValidationError("Windows display inventory exceeds its device bound.")
    finally:
        if not library.SetupDiDestroyDeviceInfoList(handle):
            raise _inventory_error("SetupDiDestroyDeviceInfoList", last_windows_error())

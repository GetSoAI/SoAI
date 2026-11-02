"""SoAI - Bounded native Windows performance counter snapshots [backend/core/hardware/windows_performance_counters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.system.windows_ctypes import load_windows_library

__all__ = ("WindowsRawCounter", "read_windows_performance_counters")

PDH_MORE_DATA = 0x800007D2
PDH_NO_DATA = 0x800007D5
PDH_CSTATUS_NO_OBJECT = 0xC0000BB8
PDH_CSTATUS_NO_COUNTER = 0xC0000BB9
PDH_CSTATUS_NO_INSTANCE = 0x800007D1


class CounterFileTime(ctypes.Structure):
    low: int = 0
    high: int = 0
    _fields_ = (("low", ctypes.c_uint32), ("high", ctypes.c_uint32))


class RawCounterValue(ctypes.Structure):
    status: int
    timestamp: CounterFileTime
    first: int
    second: int
    count: int
    _fields_ = (
        ("status", ctypes.c_uint32),
        ("timestamp", CounterFileTime),
        ("first", ctypes.c_int64),
        ("second", ctypes.c_int64),
        ("count", ctypes.c_uint32),
    )

    def __init__(self) -> None:
        super().__init__()
        self.status = self.first = self.second = self.count = 0
        self.timestamp = CounterFileTime()


class RawCounterItem(ctypes.Structure):
    name: int | None
    raw: RawCounterValue
    _fields_ = (("name", ctypes.c_void_p), ("raw", RawCounterValue))

    def __init__(self) -> None:
        super().__init__()
        self.name = None
        self.raw = RawCounterValue()


@dataclass(frozen=True, slots=True)
class WindowsRawCounter:
    name: str
    value: int
    timestamp_100ns: int


def _bind_counter_library(library: ctypes.CDLL) -> None:
    library.PdhOpenQueryW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.PdhOpenQueryW.restype = ctypes.c_uint32
    library.PdhAddEnglishCounterW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    library.PdhAddEnglishCounterW.restype = ctypes.c_uint32
    library.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
    library.PdhCollectQueryData.restype = ctypes.c_uint32
    library.PdhGetRawCounterArrayW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    ]
    library.PdhGetRawCounterArrayW.restype = ctypes.c_uint32
    library.PdhCloseQuery.argtypes = [ctypes.c_void_p]
    library.PdhCloseQuery.restype = ctypes.c_uint32


def _read_counter_name(buffer: ctypes.Array[ctypes.c_char], address: int | None) -> str:
    offset = address - ctypes.addressof(buffer) if address is not None else -1
    if offset < 0 or offset % 2 != 0 or offset + 2 > ctypes.sizeof(buffer):
        raise ValidationError("Windows counter name is outside its owned result buffer.")
    encoded = ctypes.string_at(
        ctypes.addressof(buffer) + offset, min(2048, ctypes.sizeof(buffer) - offset)
    )
    for index in range(0, len(encoded) - 1, 2):
        if encoded[index : index + 2] == b"\x00\x00":
            try:
                return encoded[:index].decode("utf-16-le")
            except UnicodeDecodeError as exception:
                raise ValidationError("Windows counter name is malformed.") from exception
    raise ValidationError("Windows counter name exceeds its result bounds.")


def _read_counter_array(
    library: ctypes.CDLL, counter: ctypes.c_void_p
) -> tuple[WindowsRawCounter, ...]:
    size = ctypes.c_uint32()
    count = ctypes.c_uint32()
    status = library.PdhGetRawCounterArrayW(counter, ctypes.byref(size), ctypes.byref(count), None)
    if status in (PDH_NO_DATA, PDH_CSTATUS_NO_INSTANCE):
        return ()
    if status not in (0, PDH_MORE_DATA):
        raise StateError("Windows counter sizing failed.", details={"native_status": status})
    for _attempt in range(3):
        if not 0 < size.value <= 16 * 1024 * 1024:
            raise ValidationError("Windows counter result size exceeds its bounded allocation.")
        buffer = ctypes.create_string_buffer(size.value)
        status = library.PdhGetRawCounterArrayW(
            counter, ctypes.byref(size), ctypes.byref(count), buffer
        )
        if status == PDH_MORE_DATA:
            continue
        if status in (PDH_NO_DATA, PDH_CSTATUS_NO_INSTANCE):
            return ()
        if status != 0:
            raise StateError("Windows counter read failed.", details={"native_status": status})
        if count.value > 65536 or count.value * ctypes.sizeof(RawCounterItem) > ctypes.sizeof(
            buffer
        ):
            raise ValidationError("Windows counter item count exceeds its owned result buffer.")
        values: list[WindowsRawCounter] = []
        names: set[str] = set()
        for index in range(count.value):
            item = RawCounterItem.from_buffer(buffer, index * ctypes.sizeof(RawCounterItem))
            if item.raw.status not in (0, 1):
                continue
            name = _read_counter_name(buffer, item.name)
            if not name or name in names or item.raw.first < 0:
                raise ValidationError("Windows counter instances are invalid or duplicated.")
            names.add(name)
            values.append(
                WindowsRawCounter(
                    name, item.raw.first, (item.raw.timestamp.high << 32) | item.raw.timestamp.low
                )
            )
        return tuple(values)
    raise StateError("Windows counter instances changed repeatedly during acquisition.")


def read_windows_performance_counters(
    paths: tuple[str, ...],
) -> dict[str, tuple[WindowsRawCounter, ...]]:
    if ctypes.sizeof(RawCounterValue) != 40 or ctypes.sizeof(RawCounterItem) != 48:
        raise ValidationError("Windows counter structures violate their native x64 ABI.")
    library = load_windows_library("pdh")
    _bind_counter_library(library)
    query = ctypes.c_void_p()
    status = library.PdhOpenQueryW(None, 0, ctypes.byref(query))
    if status != 0 or query.value is None:
        raise StateError("Windows counter query could not open.", details={"native_status": status})
    try:
        counters: dict[str, ctypes.c_void_p] = {}
        for path in paths:
            counter = ctypes.c_void_p()
            status = library.PdhAddEnglishCounterW(query, path, 0, ctypes.byref(counter))
            if status in (PDH_CSTATUS_NO_OBJECT, PDH_CSTATUS_NO_COUNTER, PDH_CSTATUS_NO_INSTANCE):
                continue
            if status != 0 or counter.value is None:
                raise StateError(
                    "Windows counter admission failed.", details={"native_status": status}
                )
            counters[path] = counter
        if not counters:
            return {}
        status = library.PdhCollectQueryData(query)
        if status == PDH_NO_DATA:
            return {}
        if status != 0:
            raise StateError(
                "Windows counter acquisition failed.", details={"native_status": status}
            )
        return {path: _read_counter_array(library, counter) for path, counter in counters.items()}
    finally:
        status = library.PdhCloseQuery(query)
        if status != 0:
            raise StateError(
                "Windows counter query release failed.", details={"native_status": status}
            )

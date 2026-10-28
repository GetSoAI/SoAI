"""SoAI - Typed retained NvAPI fan layouts [backend/hardware/vendors/nvidia/nvapi_fan_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from types import EllipsisType

__all__ = (
    "NvApiFanControlEntry",
    "NvApiFanControl",
    "NvApiFanStatusEntry",
    "NvApiFanStatus",
)


class NvApiFanControlEntry(ctypes.Structure):
    cooler_id: int
    level: int
    mode: int
    reserved: ctypes.Array[ctypes.c_uint32]

    _fields_ = (
        ("cooler_id", ctypes.c_uint32),
        ("level", ctypes.c_uint32),
        ("mode", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 8),
    )

    def __init__(
        self,
        cooler_id: int | EllipsisType = ...,
        level: int | EllipsisType = ...,
        mode: int | EllipsisType = ...,
        reserved: ctypes.Array[ctypes.c_uint32] | tuple[int, ...] | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if cooler_id is not ...:
            self.cooler_id = cooler_id
        if level is not ...:
            self.level = level
        if mode is not ...:
            self.mode = mode
        if reserved is not ...:
            self.reserved = (
                (ctypes.c_uint32 * 8)(*reserved) if isinstance(reserved, tuple) else reserved
            )


class NvApiFanControl(ctypes.Structure):
    version: int
    unknown: int
    count: int
    reserved: ctypes.Array[ctypes.c_uint32]
    entries: ctypes.Array[NvApiFanControlEntry]

    _fields_ = (
        ("version", ctypes.c_uint32),
        ("unknown", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 8),
        ("entries", NvApiFanControlEntry * 32),
    )

    def __init__(
        self,
        version: int | EllipsisType = ...,
        unknown: int | EllipsisType = ...,
        count: int | EllipsisType = ...,
        reserved: ctypes.Array[ctypes.c_uint32] | tuple[int, ...] | EllipsisType = ...,
        entries: (
            ctypes.Array[NvApiFanControlEntry] | tuple[NvApiFanControlEntry, ...] | EllipsisType
        ) = ...,
    ) -> None:
        super().__init__()
        if version is not ...:
            self.version = version
        if unknown is not ...:
            self.unknown = unknown
        if count is not ...:
            self.count = count
        if reserved is not ...:
            self.reserved = (
                (ctypes.c_uint32 * 8)(*reserved) if isinstance(reserved, tuple) else reserved
            )
        if entries is not ...:
            self.entries = (
                (NvApiFanControlEntry * 32)(*entries) if isinstance(entries, tuple) else entries
            )


class NvApiFanStatusEntry(ctypes.Structure):
    cooler_id: int
    current_rpm: int
    minimum: int
    maximum: int
    level: int
    reserved: ctypes.Array[ctypes.c_uint32]

    _fields_ = (
        ("cooler_id", ctypes.c_uint32),
        ("current_rpm", ctypes.c_uint32),
        ("minimum", ctypes.c_uint32),
        ("maximum", ctypes.c_uint32),
        ("level", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 8),
    )

    def __init__(
        self,
        cooler_id: int | EllipsisType = ...,
        current_rpm: int | EllipsisType = ...,
        minimum: int | EllipsisType = ...,
        maximum: int | EllipsisType = ...,
        level: int | EllipsisType = ...,
        reserved: ctypes.Array[ctypes.c_uint32] | tuple[int, ...] | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if cooler_id is not ...:
            self.cooler_id = cooler_id
        if current_rpm is not ...:
            self.current_rpm = current_rpm
        if minimum is not ...:
            self.minimum = minimum
        if maximum is not ...:
            self.maximum = maximum
        if level is not ...:
            self.level = level
        if reserved is not ...:
            self.reserved = (
                (ctypes.c_uint32 * 8)(*reserved) if isinstance(reserved, tuple) else reserved
            )


class NvApiFanStatus(ctypes.Structure):
    version: int
    count: int
    reserved: ctypes.Array[ctypes.c_uint32]
    entries: ctypes.Array[NvApiFanStatusEntry]

    _fields_ = (
        ("version", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 8),
        ("entries", NvApiFanStatusEntry * 32),
    )

    def __init__(
        self,
        version: int | EllipsisType = ...,
        count: int | EllipsisType = ...,
        reserved: ctypes.Array[ctypes.c_uint32] | tuple[int, ...] | EllipsisType = ...,
        entries: (
            ctypes.Array[NvApiFanStatusEntry] | tuple[NvApiFanStatusEntry, ...] | EllipsisType
        ) = ...,
    ) -> None:
        super().__init__()
        if version is not ...:
            self.version = version
        if count is not ...:
            self.count = count
        if reserved is not ...:
            self.reserved = (
                (ctypes.c_uint32 * 8)(*reserved) if isinstance(reserved, tuple) else reserved
            )
        if entries is not ...:
            self.entries = (
                (NvApiFanStatusEntry * 32)(*entries) if isinstance(entries, tuple) else entries
            )

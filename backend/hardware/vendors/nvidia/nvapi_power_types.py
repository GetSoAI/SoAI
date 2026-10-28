"""SoAI - Typed retained NvAPI power policy layouts [backend/hardware/vendors/nvidia/nvapi_power_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from types import EllipsisType

__all__ = (
    "NvApiPowerInfoEntry",
    "NvApiPowerInfo",
    "NvApiPowerStatusEntry",
    "NvApiPowerStatus",
)


class NvApiPowerInfoEntry(ctypes.Structure):
    pstate: int
    reserved_first: ctypes.Array[ctypes.c_uint32]
    minimum: int
    reserved_second: ctypes.Array[ctypes.c_uint32]
    default: int
    reserved_third: ctypes.Array[ctypes.c_uint32]
    maximum: int
    reserved_last: int

    _fields_ = (
        ("pstate", ctypes.c_uint32),
        ("reserved_first", ctypes.c_uint32 * 2),
        ("minimum", ctypes.c_uint32),
        ("reserved_second", ctypes.c_uint32 * 2),
        ("default", ctypes.c_uint32),
        ("reserved_third", ctypes.c_uint32 * 2),
        ("maximum", ctypes.c_uint32),
        ("reserved_last", ctypes.c_uint32),
    )

    def __init__(
        self,
        pstate: int | EllipsisType = ...,
        reserved_first: ctypes.Array[ctypes.c_uint32] | tuple[int, ...] | EllipsisType = ...,
        minimum: int | EllipsisType = ...,
        reserved_second: ctypes.Array[ctypes.c_uint32] | tuple[int, ...] | EllipsisType = ...,
        default: int | EllipsisType = ...,
        reserved_third: ctypes.Array[ctypes.c_uint32] | tuple[int, ...] | EllipsisType = ...,
        maximum: int | EllipsisType = ...,
        reserved_last: int | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if pstate is not ...:
            self.pstate = pstate
        if reserved_first is not ...:
            self.reserved_first = (
                (ctypes.c_uint32 * 2)(*reserved_first)
                if isinstance(reserved_first, tuple)
                else reserved_first
            )
        if minimum is not ...:
            self.minimum = minimum
        if reserved_second is not ...:
            self.reserved_second = (
                (ctypes.c_uint32 * 2)(*reserved_second)
                if isinstance(reserved_second, tuple)
                else reserved_second
            )
        if default is not ...:
            self.default = default
        if reserved_third is not ...:
            self.reserved_third = (
                (ctypes.c_uint32 * 2)(*reserved_third)
                if isinstance(reserved_third, tuple)
                else reserved_third
            )
        if maximum is not ...:
            self.maximum = maximum
        if reserved_last is not ...:
            self.reserved_last = reserved_last


class NvApiPowerInfo(ctypes.Structure):
    version: int
    valid: int
    count: int
    padding: ctypes.Array[ctypes.c_uint8]
    entries: ctypes.Array[NvApiPowerInfoEntry]

    _fields_ = (
        ("version", ctypes.c_uint32),
        ("valid", ctypes.c_uint8),
        ("count", ctypes.c_uint8),
        ("padding", ctypes.c_uint8 * 2),
        ("entries", NvApiPowerInfoEntry * 4),
    )

    def __init__(
        self,
        version: int | EllipsisType = ...,
        valid: int | EllipsisType = ...,
        count: int | EllipsisType = ...,
        padding: ctypes.Array[ctypes.c_uint8] | tuple[int, ...] | EllipsisType = ...,
        entries: (
            ctypes.Array[NvApiPowerInfoEntry] | tuple[NvApiPowerInfoEntry, ...] | EllipsisType
        ) = ...,
    ) -> None:
        super().__init__()
        if version is not ...:
            self.version = version
        if valid is not ...:
            self.valid = valid
        if count is not ...:
            self.count = count
        if padding is not ...:
            self.padding = (ctypes.c_uint8 * 2)(*padding) if isinstance(padding, tuple) else padding
        if entries is not ...:
            self.entries = (
                (NvApiPowerInfoEntry * 4)(*entries) if isinstance(entries, tuple) else entries
            )


class NvApiPowerStatusEntry(ctypes.Structure):
    reserved_first: int
    reserved_second: int
    power: int
    reserved_last: int

    _fields_ = (
        ("reserved_first", ctypes.c_uint32),
        ("reserved_second", ctypes.c_uint32),
        ("power", ctypes.c_uint32),
        ("reserved_last", ctypes.c_uint32),
    )

    def __init__(
        self,
        reserved_first: int | EllipsisType = ...,
        reserved_second: int | EllipsisType = ...,
        power: int | EllipsisType = ...,
        reserved_last: int | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if reserved_first is not ...:
            self.reserved_first = reserved_first
        if reserved_second is not ...:
            self.reserved_second = reserved_second
        if power is not ...:
            self.power = power
        if reserved_last is not ...:
            self.reserved_last = reserved_last


class NvApiPowerStatus(ctypes.Structure):
    version: int
    count: int
    entries: ctypes.Array[NvApiPowerStatusEntry]

    _fields_ = (
        ("version", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
        ("entries", NvApiPowerStatusEntry * 4),
    )

    def __init__(
        self,
        version: int | EllipsisType = ...,
        count: int | EllipsisType = ...,
        entries: (
            ctypes.Array[NvApiPowerStatusEntry] | tuple[NvApiPowerStatusEntry, ...] | EllipsisType
        ) = ...,
    ) -> None:
        super().__init__()
        if version is not ...:
            self.version = version
        if count is not ...:
            self.count = count
        if entries is not ...:
            self.entries = (
                (NvApiPowerStatusEntry * 4)(*entries) if isinstance(entries, tuple) else entries
            )

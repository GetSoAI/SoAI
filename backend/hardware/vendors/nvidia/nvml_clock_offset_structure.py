"""SoAI - NVML native clock-offset structure and supplied-field inputs [backend/hardware/vendors/nvidia/nvml_clock_offset_structure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from types import EllipsisType
from typing import TypedDict, Unpack

__all__ = ("NvmlClockOffset",)


class NvmlClockOffsetTypeInput(TypedDict, total=False):
    type: int


class NvmlClockOffset(ctypes.Structure):
    version: int
    type: int
    pstate: int
    clock_offset_mhz: int
    min_clock_offset_mhz: int
    max_clock_offset_mhz: int

    _fields_ = (
        ("version", ctypes.c_uint),
        ("type", ctypes.c_uint),
        ("pstate", ctypes.c_uint),
        ("clock_offset_mhz", ctypes.c_int),
        ("min_clock_offset_mhz", ctypes.c_int),
        ("max_clock_offset_mhz", ctypes.c_int),
    )

    def __init__(
        self,
        version: int | EllipsisType = ...,
        clock_type: int | EllipsisType = ...,
        pstate: int | EllipsisType = ...,
        clock_offset_mhz: int | EllipsisType = ...,
        min_clock_offset_mhz: int | EllipsisType = ...,
        max_clock_offset_mhz: int | EllipsisType = ...,
        **named_fields: Unpack[NvmlClockOffsetTypeInput],
    ) -> None:
        super().__init__()
        if version is not ...:
            self.version = version
        if any(name != "type" for name in named_fields):
            raise TypeError("NVML clock offsets require declared native inputs.")
        if "type" in named_fields:
            if clock_type is not ...:
                raise TypeError("NVML clock type received duplicate native inputs.")
            clock_type = named_fields["type"]
        if clock_type is not ...:
            self.type = clock_type
        if pstate is not ...:
            self.pstate = pstate
        if clock_offset_mhz is not ...:
            self.clock_offset_mhz = clock_offset_mhz
        if min_clock_offset_mhz is not ...:
            self.min_clock_offset_mhz = min_clock_offset_mhz
        if max_clock_offset_mhz is not ...:
            self.max_clock_offset_mhz = max_clock_offset_mhz

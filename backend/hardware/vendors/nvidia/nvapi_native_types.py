"""SoAI - Typed retained NvAPI clock and P-state layouts [backend/hardware/vendors/nvidia/nvapi_native_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from types import EllipsisType
from typing import TypedDict, Unpack, overload

__all__ = (
    "NvApiClockDelta",
    "NvApiClockRange",
    "NvApiClockData",
    "NvApiClockEntry",
    "NvApiVoltageEntry",
    "NvApiPstate",
    "NvApiPstates",
)


class NvApiClockDelta(ctypes.Structure):
    value: int
    minimum: int
    maximum: int

    _fields_ = (
        ("value", ctypes.c_int32),
        ("minimum", ctypes.c_int32),
        ("maximum", ctypes.c_int32),
    )

    def __init__(
        self,
        value: int | EllipsisType = ...,
        minimum: int | EllipsisType = ...,
        maximum: int | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if value is not ...:
            self.value = value
        if minimum is not ...:
            self.minimum = minimum
        if maximum is not ...:
            self.maximum = maximum


class NvApiClockRange(ctypes.Structure):
    minimum_frequency: int
    maximum_frequency: int
    voltage_domain: int
    minimum_voltage: int
    maximum_voltage: int

    _fields_ = (
        ("minimum_frequency", ctypes.c_uint32),
        ("maximum_frequency", ctypes.c_uint32),
        ("voltage_domain", ctypes.c_int32),
        ("minimum_voltage", ctypes.c_uint32),
        ("maximum_voltage", ctypes.c_uint32),
    )

    def __init__(
        self,
        minimum_frequency: int | EllipsisType = ...,
        maximum_frequency: int | EllipsisType = ...,
        voltage_domain: int | EllipsisType = ...,
        minimum_voltage: int | EllipsisType = ...,
        maximum_voltage: int | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if minimum_frequency is not ...:
            self.minimum_frequency = minimum_frequency
        if maximum_frequency is not ...:
            self.maximum_frequency = maximum_frequency
        if voltage_domain is not ...:
            self.voltage_domain = voltage_domain
        if minimum_voltage is not ...:
            self.minimum_voltage = minimum_voltage
        if maximum_voltage is not ...:
            self.maximum_voltage = maximum_voltage


class NvApiClockDataInput(TypedDict, total=False):
    frequency: int
    range: NvApiClockRange | tuple[int, ...]


class NvApiClockTypeInput(TypedDict, total=False):
    type: int


class NvApiClockData(ctypes.Union):
    frequency: int
    range: NvApiClockRange

    _fields_ = (("frequency", ctypes.c_uint32), ("range", NvApiClockRange))

    @overload
    def __init__(
        self,
        frequency: int,
        range_value: NvApiClockRange | tuple[int, ...] = ...,
        /,
        **named_fields: Unpack[NvApiClockDataInput],
    ) -> None: ...

    @overload
    def __init__(self, **named_fields: Unpack[NvApiClockDataInput]) -> None: ...

    def __init__(
        self,
        *native_fields: int | NvApiClockRange | tuple[int, ...],
        **named_fields: Unpack[NvApiClockDataInput],
    ) -> None:
        super().__init__()
        if len(native_fields) > 2:
            raise TypeError("NvAPI clock data requires at most two native union fields.")
        if native_fields:
            frequency = native_fields[0]
            if not isinstance(frequency, int):
                raise TypeError("NvAPI frequency requires a native integer input.")
            self.frequency = frequency
        if len(native_fields) == 2:
            range_value = native_fields[1]
            if not isinstance(range_value, NvApiClockRange | tuple):
                raise TypeError("NvAPI clock range requires native range inputs.")
            self.range = (
                NvApiClockRange(*range_value) if isinstance(range_value, tuple) else range_value
            )
        for name in named_fields:
            if name == "frequency":
                frequency_value = named_fields.get("frequency")
                if native_fields:
                    raise TypeError("NvAPI frequency received duplicate native inputs.")
                if not isinstance(frequency_value, int):
                    raise TypeError("NvAPI frequency requires a native integer input.")
                self.frequency = frequency_value
            elif name == "range":
                named_range = named_fields.get("range")
                if len(native_fields) == 2:
                    raise TypeError("NvAPI clock range received duplicate native inputs.")
                if not isinstance(named_range, NvApiClockRange | tuple):
                    raise TypeError("NvAPI clock range requires native range inputs.")
                self.range = (
                    NvApiClockRange(*named_range) if isinstance(named_range, tuple) else named_range
                )
            else:
                raise TypeError("NvAPI clock data requires declared frequency or range inputs.")


class NvApiClockEntry(ctypes.Structure):
    domain: int
    type: int
    editable: int
    delta: NvApiClockDelta
    data: NvApiClockData

    _fields_ = (
        ("domain", ctypes.c_int32),
        ("type", ctypes.c_int32),
        ("editable", ctypes.c_uint32),
        ("delta", NvApiClockDelta),
        ("data", NvApiClockData),
    )

    def __init__(
        self,
        domain: int | EllipsisType = ...,
        clock_type: int | EllipsisType = ...,
        editable: int | EllipsisType = ...,
        delta: NvApiClockDelta | tuple[int, ...] | EllipsisType = ...,
        data: (
            NvApiClockData
            | tuple[()]
            | tuple[int]
            | tuple[int, NvApiClockRange | tuple[int, ...]]
            | EllipsisType
        ) = ...,
        **named_fields: Unpack[NvApiClockTypeInput],
    ) -> None:
        super().__init__()
        if domain is not ...:
            self.domain = domain
        if any(name != "type" for name in named_fields):
            raise TypeError("NvAPI clock entries require declared native inputs.")
        if "type" in named_fields:
            if clock_type is not ...:
                raise TypeError("NvAPI clock type received duplicate native inputs.")
            clock_type = named_fields["type"]
        if clock_type is not ...:
            self.type = clock_type
        if editable is not ...:
            self.editable = editable
        if delta is not ...:
            self.delta = NvApiClockDelta(*delta) if isinstance(delta, tuple) else delta
        if data is not ...:
            if isinstance(data, tuple):
                if not data:
                    self.data = NvApiClockData()
                elif len(data) == 1:
                    self.data = NvApiClockData(data[0])
                elif len(data) == 2:
                    self.data = NvApiClockData(data[0], data[1])
                else:
                    raise TypeError("NvAPI clock data requires at most two native union fields.")
            else:
                self.data = data


class NvApiVoltageEntry(ctypes.Structure):
    domain: int
    editable: int
    voltage: int
    delta: NvApiClockDelta

    _fields_ = (
        ("domain", ctypes.c_int32),
        ("editable", ctypes.c_uint32),
        ("voltage", ctypes.c_uint32),
        ("delta", NvApiClockDelta),
    )

    def __init__(
        self,
        domain: int | EllipsisType = ...,
        editable: int | EllipsisType = ...,
        voltage: int | EllipsisType = ...,
        delta: NvApiClockDelta | tuple[int, ...] | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if domain is not ...:
            self.domain = domain
        if editable is not ...:
            self.editable = editable
        if voltage is not ...:
            self.voltage = voltage
        if delta is not ...:
            self.delta = NvApiClockDelta(*delta) if isinstance(delta, tuple) else delta


class NvApiPstate(ctypes.Structure):
    pstate: int
    editable: int
    clocks: ctypes.Array[NvApiClockEntry]
    voltages: ctypes.Array[NvApiVoltageEntry]

    _fields_ = (
        ("pstate", ctypes.c_int32),
        ("editable", ctypes.c_uint32),
        ("clocks", NvApiClockEntry * 8),
        ("voltages", NvApiVoltageEntry * 4),
    )

    def __init__(
        self,
        pstate: int | EllipsisType = ...,
        editable: int | EllipsisType = ...,
        clocks: ctypes.Array[NvApiClockEntry] | tuple[NvApiClockEntry, ...] | EllipsisType = ...,
        voltages: (
            ctypes.Array[NvApiVoltageEntry] | tuple[NvApiVoltageEntry, ...] | EllipsisType
        ) = ...,
    ) -> None:
        super().__init__()
        if pstate is not ...:
            self.pstate = pstate
        if editable is not ...:
            self.editable = editable
        if clocks is not ...:
            self.clocks = (NvApiClockEntry * 8)(*clocks) if isinstance(clocks, tuple) else clocks
        if voltages is not ...:
            self.voltages = (
                (NvApiVoltageEntry * 4)(*voltages) if isinstance(voltages, tuple) else voltages
            )


class NvApiPstates(ctypes.Structure):
    version: int
    editable: int
    pstate_count: int
    clock_count: int
    voltage_count: int
    pstates: ctypes.Array[NvApiPstate]

    _fields_ = (
        ("version", ctypes.c_uint32),
        ("editable", ctypes.c_uint32),
        ("pstate_count", ctypes.c_uint32),
        ("clock_count", ctypes.c_uint32),
        ("voltage_count", ctypes.c_uint32),
        ("pstates", NvApiPstate * 16),
    )

    def __init__(
        self,
        version: int | EllipsisType = ...,
        editable: int | EllipsisType = ...,
        pstate_count: int | EllipsisType = ...,
        clock_count: int | EllipsisType = ...,
        voltage_count: int | EllipsisType = ...,
        pstates: ctypes.Array[NvApiPstate] | tuple[NvApiPstate, ...] | EllipsisType = ...,
    ) -> None:
        super().__init__()
        if version is not ...:
            self.version = version
        if editable is not ...:
            self.editable = editable
        if pstate_count is not ...:
            self.pstate_count = pstate_count
        if clock_count is not ...:
            self.clock_count = clock_count
        if voltage_count is not ...:
            self.voltage_count = voltage_count
        if pstates is not ...:
            self.pstates = (NvApiPstate * 16)(*pstates) if isinstance(pstates, tuple) else pstates

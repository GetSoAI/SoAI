"""SoAI - Native NvAPI dynamic utilization layout [backend/hardware/vendors/nvidia/nvapi_sensor_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes

__all__ = ("NvApiUtilizationDomain", "NvApiDynamicPstates")


class NvApiUtilizationDomain(ctypes.Structure):
    present: int
    percentage: int
    _fields_ = (("present", ctypes.c_uint32), ("percentage", ctypes.c_uint32))

    def __init__(self) -> None:
        super().__init__()
        self.present = 0
        self.percentage = 0


class NvApiDynamicPstates(ctypes.Structure):
    version: int
    flags: int
    utilization: ctypes.Array[NvApiUtilizationDomain]
    _fields_ = (
        ("version", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("utilization", NvApiUtilizationDomain * 8),
    )

    def __init__(self) -> None:
        super().__init__()
        self.version = 0
        self.flags = 0
        self.utilization = (NvApiUtilizationDomain * 8)()

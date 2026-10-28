"""SoAI - ADL shared-memory PMLog ABI and lease state [backend/hardware/vendors/amd/adl_pmlog_abi.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field

__all__ = ("AdlPMLogOutput", "AdlPMLogLease")


class AdlPMLogSensor(ctypes.Structure):
    _fields_ = (("supported", ctypes.c_int32), ("value", ctypes.c_int32))


class AdlPMLogOutput(ctypes.Structure):
    _fields_ = (("size", ctypes.c_int32), ("sensors", AdlPMLogSensor * 256))


@dataclass(slots=True)
class AdlPMLogLease:
    adapter_index: int
    handle: ctypes.c_uint32 = field(default_factory=ctypes.c_uint32)
    shared_memory: ctypes.c_void_p = field(default_factory=ctypes.c_void_p)
    start_attempted: bool = False
    stop_attempted: bool = False
    destroy_attempted: bool = False

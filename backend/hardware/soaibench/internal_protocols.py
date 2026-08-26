"""SoAI - SoAIBench internal protocol definitions [backend/hardware/soaibench/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from hardware.vendors.nvidia.internal_protocols import NvmlPciInfoProtocol

__all__ = ("NvidiaTelemetryNvmlModuleProtocol",)


@runtime_checkable
class NvidiaTelemetryNvmlModuleProtocol(Protocol):
    NVMLError: type[Exception]
    nvmlDeviceGetCount: Callable[[], int]
    nvmlDeviceGetHandleByIndex: Callable[[int], ctypes.c_void_p]
    nvmlDeviceGetPciInfo: Callable[[ctypes.c_void_p], NvmlPciInfoProtocol]

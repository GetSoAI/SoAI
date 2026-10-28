"""SoAI - Product-neutral OpenCL discovery outcomes [backend/core/hardware/opencl_runtime_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.hardware.gpu_physical_identity import GPUVendorObservation

__all__ = (
    "OpenCLRuntimeState",
    "OpenCLRuntimeTarget",
    "OpenCLRuntimeSnapshot",
)


class OpenCLRuntimeState(StrEnum):
    READY = "ready"
    PERMISSION_DENIED = "permission_denied"
    ZERO_DEVICES = "zero_devices"
    UNSUPPORTED = "unsupported"
    IDENTITY_CONFLICT = "identity_conflict"
    UNAVAILABLE = "unavailable"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class OpenCLRuntimeTarget:
    device_id: str
    vendor: str
    state: OpenCLRuntimeState
    reason_code: str | None
    message: str
    match_basis: str | None
    platform_name: str | None
    driver_version: str | None
    effective_uid: int | None
    effective_gid: int | None


@dataclass(frozen=True, slots=True)
class OpenCLRuntimeSnapshot:
    acquisition_id: str
    targets: tuple[OpenCLRuntimeTarget, ...]
    vendor_observations: tuple[GPUVendorObservation, ...] = ()

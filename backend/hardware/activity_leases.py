"""SoAI - Shared hardware activity lease types [backend/hardware/activity_leases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.hardware.protocols_activity import HardwareActivityConflictProtocol

__all__ = (
    "HardwareActivityConflict",
    "HardwareActivityLease",
    "lease_conflict_payload",
)


@dataclass(frozen=True, slots=True)
class HardwareActivityLease:
    device_id: str
    lease_id: str
    activity_type: str
    owner_id: str
    run_id: str | None = None
    degraded: bool = False


@dataclass(frozen=True, slots=True)
class HardwareActivityConflict:
    device_id: str
    active_activity_type: str
    conflict_reason: str


def lease_conflict_payload(conflict: HardwareActivityConflictProtocol) -> JSONDict:
    return {
        "success": False,
        "accepted": False,
        "active": True,
        "device_id": conflict.device_id,
        "conflict_reason": _public_conflict_reason(conflict),
        "active_activity_type": conflict.active_activity_type,
    }


def _public_conflict_reason(conflict: HardwareActivityConflictProtocol) -> str:
    if conflict.active_activity_type == "mutation":
        return "gpu_tuning_active"
    return conflict.conflict_reason

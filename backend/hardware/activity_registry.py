"""SoAI - Shared per-device hardware activity registry [backend/hardware/activity_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from hardware.activity_leases import HardwareActivityConflict, HardwareActivityLease

__all__ = (
    "HardwareActivityAcquireResult",
    "HardwareActivityRegistry",
    "HardwareActivityRegistryDependencies",
)


@dataclass(frozen=True, slots=True)
class HardwareActivityAcquireResult:
    lease: HardwareActivityLease | None
    conflict: HardwareActivityConflict | None


@dataclass(frozen=True, slots=True)
class HardwareActivityRegistryDependencies:
    def __post_init__(self) -> None:
        require_dependencies(owner="HardwareActivityRegistryDependencies")


class HardwareActivityRegistry:
    def __init__(self, deps: HardwareActivityRegistryDependencies) -> None:
        self._deps = deps
        self._lock = asyncio.Lock()
        self._leases_by_device: dict[str, HardwareActivityLease] = {}

    async def acquire(
        self,
        *,
        device_id: str,
        activity_type: str,
        owner_id: str,
        conflict_reason: str,
    ) -> HardwareActivityAcquireResult:
        normalized_device_id = _require_non_empty(device_id, "device_id")
        normalized_activity_type = _require_non_empty(activity_type, "activity_type")
        normalized_owner_id = _require_non_empty(owner_id, "owner_id")
        normalized_conflict_reason = _require_non_empty(conflict_reason, "conflict_reason")
        async with self._lock:
            active = self._leases_by_device.get(normalized_device_id)
            if active is not None:
                return HardwareActivityAcquireResult(
                    lease=None,
                    conflict=HardwareActivityConflict(
                        device_id=normalized_device_id,
                        active_activity_type=active.activity_type,
                        conflict_reason=normalized_conflict_reason,
                    ),
                )
            lease = HardwareActivityLease(
                device_id=normalized_device_id,
                lease_id=uuid.uuid4().hex,
                activity_type=normalized_activity_type,
                owner_id=normalized_owner_id,
            )
            self._leases_by_device[normalized_device_id] = lease
            return HardwareActivityAcquireResult(lease=lease, conflict=None)

    async def bind_run_id(self, *, device_id: str, lease_id: str, run_id: str) -> bool:
        normalized_device_id = _require_non_empty(device_id, "device_id")
        normalized_lease_id = _require_non_empty(lease_id, "lease_id")
        normalized_run_id = _require_non_empty(run_id, "run_id")
        async with self._lock:
            active = self._leases_by_device.get(normalized_device_id)
            if active is None or active.lease_id != normalized_lease_id:
                return False
            self._leases_by_device[normalized_device_id] = HardwareActivityLease(
                device_id=active.device_id,
                lease_id=active.lease_id,
                activity_type=active.activity_type,
                owner_id=active.owner_id,
                run_id=normalized_run_id,
                degraded=active.degraded,
            )
            return True

    async def mark_degraded(self, *, device_id: str, lease_id: str, reason: str) -> bool:
        normalized_device_id = _require_non_empty(device_id, "device_id")
        normalized_lease_id = _require_non_empty(lease_id, "lease_id")
        _require_non_empty(reason, "reason")
        async with self._lock:
            active = self._leases_by_device.get(normalized_device_id)
            if active is None or active.lease_id != normalized_lease_id:
                return False
            if active.degraded:
                return True
            self._leases_by_device[normalized_device_id] = HardwareActivityLease(
                device_id=active.device_id,
                lease_id=active.lease_id,
                activity_type=active.activity_type,
                owner_id=active.owner_id,
                run_id=active.run_id,
                degraded=True,
            )
            return True

    async def release(self, *, device_id: str, lease_id: str) -> bool:
        normalized_device_id = _require_non_empty(device_id, "device_id")
        normalized_lease_id = _require_non_empty(lease_id, "lease_id")
        async with self._lock:
            active = self._leases_by_device.get(normalized_device_id)
            if active is None or active.lease_id != normalized_lease_id:
                return False
            self._leases_by_device.pop(normalized_device_id, None)
            return True

    async def clear(self) -> None:
        async with self._lock:
            self._leases_by_device.clear()


def _require_non_empty(value: str, label: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValidationError(f"{label} is required.")
    return normalized

"""SoAI - GPU tuning mutation activity leases [backend/hardware/gpu_tuning/mutation_leases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ValidationError
from core.hardware.protocols_activity import (
    HardwareActivityConflictProtocol,
    HardwareActivityRegistryProtocol,
)
from core.types.json import JSONDict

__all__ = (
    "gpu_mutation_conflict_payload",
    "run_json_with_gpu_mutation_lease",
)


async def run_json_with_gpu_mutation_lease(
    *,
    activity_registry: HardwareActivityRegistryProtocol,
    device_id: str,
    owner_id: str,
    operation: Callable[[], Awaitable[JSONDict]],
) -> JSONDict:
    acquire = await activity_registry.acquire(
        device_id=device_id,
        activity_type="mutation",
        owner_id=owner_id,
        conflict_reason="gpu_tuning_active",
    )
    if acquire.conflict is not None:
        return gpu_mutation_conflict_payload(acquire.conflict)
    if acquire.lease is None:
        raise ValidationError("GPU mutation activity lease acquisition failed.")
    try:
        return await operation()
    finally:
        await uncancel_then_cleanup(
            activity_registry.release(
                device_id=acquire.lease.device_id,
                lease_id=acquire.lease.lease_id,
            ),
        )


def gpu_mutation_conflict_payload(conflict: HardwareActivityConflictProtocol) -> JSONDict:
    return {
        "success": False,
        "code": "gpu_activity_conflict",
        "error": "GPU activity is already running for this device.",
        "device_id": conflict.device_id,
        "conflict_reason": _public_conflict_reason(conflict),
        "active_activity_type": conflict.active_activity_type,
    }


def _public_conflict_reason(conflict: HardwareActivityConflictProtocol) -> str:
    if conflict.active_activity_type.startswith("soaibench"):
        return "soaibench_active"
    return conflict.conflict_reason

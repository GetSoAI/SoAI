"""SoAI - GPU tuning mutation activity leases [backend/hardware/gpu_tuning/mutation_leases.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial

from core.concurrency.cancellation_cleanup import run_idempotent_current_task_operation
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.protocols_activity import (
    HardwareActivityConflictProtocol,
    HardwareActivityLeaseProtocol,
    HardwareActivityRegistryProtocol,
)
from core.types.json import JSONDict
from core.validation.strings import require_canonical_trimmed_json_text

__all__ = (
    "gpu_mutation_conflict_payload",
    "run_json_with_gpu_mutation_lease",
    "release_gpu_control_leases",
)


GPU_CONTROL_LEASE_RELEASE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    ExceptionGroup,
)


@dataclass(frozen=True, slots=True)
class GPUControlMetadataScope:
    device_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.device_ids, tuple) or not self.device_ids:
            raise ValidationError("GPU metadata requires complete canonical device identifiers.")
        for device_id in self.device_ids:
            require_canonical_trimmed_json_text(
                device_id, error_message="GPU metadata device ID is invalid."
            )
        if len(set(self.device_ids)) != len(self.device_ids):
            raise ValidationError("GPU metadata device identifiers must be distinct.")


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
        await release_gpu_control_leases(activity_registry, (acquire.lease,))


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


async def release_gpu_control_leases(
    registry: HardwareActivityRegistryProtocol, leases: tuple[HardwareActivityLeaseProtocol, ...]
) -> None:
    failures: list[Exception] = []
    for lease in reversed(leases):
        try:
            released = await run_idempotent_current_task_operation(
                partial(registry.release, device_id=lease.device_id, lease_id=lease.lease_id),
            )
            if not released:
                failures.append(
                    ValidationError(
                        "GPU owned lease changed before release.",
                        details={"device_id": lease.device_id, "lease_id": lease.lease_id},
                    )
                )
        except GPU_CONTROL_LEASE_RELEASE_EXCEPTIONS as exception:
            exception.add_note(f"GPU lease cleanup: {lease.device_id}/{lease.lease_id}")
            failures.append(exception)
    if failures:
        raise ExceptionGroup("GPU owned lease cleanup failed.", failures)

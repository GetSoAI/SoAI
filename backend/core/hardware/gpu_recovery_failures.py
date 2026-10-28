"""SoAI - Explicit GPU recovery target conflicts [backend/core/hardware/gpu_recovery_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryRecord
from core.types.json import JSONDict

__all__ = ("GPURecoveryTargetConflictError", "gpu_recovery_target_conflict_details")


class GPURecoveryTargetConflictError(ValidationError):
    code: str | int = "gpu_recovery_identity_conflict"
    public_message: str | None = (
        "GPU recovery cannot verify the physical target. GPU changes remain disabled. Preserve the recovery data and review the hardware diagnostics."
    )


def gpu_recovery_target_conflict_details(
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    *,
    expected_uuid: str | None,
    actual_uuid: str | None,
    expected_pci: str | None,
    actual_pci: str | None,
) -> JSONDict:
    expected, actual = record.physical_identity, target.identity

    return {
        "operation_id": record.operation_id,
        "expected": {
            "device_id": record.device_id,
            "uuid": expected_uuid,
            "raw_uuid": expected.uuid,
            "pci_bdf_full": expected_pci,
            "raw_pci_bdf_full": expected.pci_bdf_full,
            "native_device_path": expected.native_device_path,
            "windows_pnp_instance_id": expected.windows_pnp_instance_id,
            "pci_bdf_observations": (
                list(record.pci_bdf_observations)
                if record.pci_bdf_observations is not None
                else None
            ),
        },
        "actual": {
            "device_id": target.device_id,
            "uuid": actual_uuid,
            "raw_uuid": actual.uuid,
            "pci_bdf_full": actual_pci,
            "raw_pci_bdf_full": actual.pci_bdf_full,
            "native_device_path": actual.native_device_path,
            "windows_pnp_instance_id": actual.windows_pnp_instance_id,
            "pci_bdf_observations": list(target.pci_bdf_observations),
        },
    }

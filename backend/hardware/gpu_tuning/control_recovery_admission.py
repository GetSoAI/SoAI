"""SoAI - GPU physical admission and duplicate mutation authority [backend/hardware/gpu_tuning/control_recovery_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import GPURecoveryAdmission, GPURecoveryAdmissionState
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalIdentity,
)
from core.hardware.gpu_recovery_records import (
    GPURecoveryRecord,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.types.json import JSONDict
from hardware.gpu_inventory.physical_binding import match_gpu_physical_identity

__all__ = (
    "inspect_recovery_records",
    "require_distinct_control_targets",
)


def inspect_recovery_records(
    target: GPUPhysicalDevice,
    records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> GPURecoveryAdmission:
    selected: JSONDict = {
        "uuid": target.identity.uuid,
        "pci_bdf_full": target.identity.pci_bdf_full,
        "windows_pnp_instance_id": target.identity.windows_pnp_instance_id,
        "pci_bdf_observations": list(target.pci_bdf_observations),
    }
    matches: list[str] = []
    for record in records:
        if isinstance(record, GPUStartupRecoveryRecord):
            original, legacy = record.original_record, record.legacy_record
            identity = GPUPhysicalIdentity(
                original.physical_identity.uuid or legacy.physical_identity.uuid,
                original.physical_identity.pci_bdf_full or legacy.physical_identity.pci_bdf_full,
                windows_pnp_instance_id=original.physical_identity.windows_pnp_instance_id
                or legacy.physical_identity.windows_pnp_instance_id,
            )
            observations: tuple[str, ...] | None = tuple(
                observation
                for child in (original, legacy)
                for observation in (child.pci_bdf_observations or ())
            )
            operation_id = record.startup_operation_id
        elif isinstance(record, GPUStartupLegacyRecoveryRecord):
            legacy = record.legacy_record
            identity, observations = legacy.physical_identity, legacy.pci_bdf_observations
            operation_id = record.startup_operation_id
        else:
            identity, observations = record.physical_identity, record.pci_bdf_observations
            operation_id = record.operation_id
        candidate: JSONDict = {
            "uuid": identity.uuid,
            "pci_bdf_full": identity.pci_bdf_full,
            "windows_pnp_instance_id": identity.windows_pnp_instance_id,
        }
        if observations is not None:
            candidate["pci_bdf_observations"] = list(observations)
        relation = match_gpu_physical_identity(selected, candidate)
        if relation in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ) or (record.device_id == target.device_id and relation != GPUPhysicalBindingState.BOUND):
            return GPURecoveryAdmission(GPURecoveryAdmissionState.IDENTITY_CONFLICT, operation_id)
        if relation == GPUPhysicalBindingState.BOUND:
            matches.append(operation_id)
    if len(matches) > 1:
        return GPURecoveryAdmission(GPURecoveryAdmissionState.IDENTITY_CONFLICT, None)
    if matches:
        return GPURecoveryAdmission(GPURecoveryAdmissionState.RECOVERY_REQUIRED, matches[0])
    return GPURecoveryAdmission(GPURecoveryAdmissionState.CLEAR, None)


def require_distinct_control_targets(targets: tuple[GPUPhysicalDevice, ...]) -> None:
    if not isinstance(targets, tuple) or not targets:
        raise ValidationError("GPU mutation requires a complete canonical target batch.")
    device_ids: set[str] = set()
    uuids: set[str] = set()
    addresses: set[str] = set()
    pnp_instances: set[str] = set()
    for target in targets:
        identity = target.identity
        uuid = identity.uuid.casefold() if identity.uuid is not None else None
        address = (
            normalize_observed_full_pci_bdf(identity.pci_bdf_full)
            if identity.pci_bdf_full is not None
            else None
        )
        duplicate_pnp = (
            identity.windows_pnp_instance_id is not None
            and identity.windows_pnp_instance_id in pnp_instances
        )
        duplicate_uuid = uuid is not None and uuid in uuids
        if (
            target.device_id in device_ids
            or duplicate_uuid
            or (address and address in addresses)
            or duplicate_pnp
        ):
            raise ValidationError("GPU mutation batch contains duplicate physical authority.")
        device_ids.add(target.device_id)
        if identity.windows_pnp_instance_id is not None:
            pnp_instances.add(identity.windows_pnp_instance_id)
        if uuid is not None:
            uuids.add(uuid)
        if address:
            addresses.add(address)

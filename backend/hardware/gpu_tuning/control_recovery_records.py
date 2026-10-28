"""SoAI - Frozen GPU control records and saved-state authority [backend/hardware/gpu_tuning/control_recovery_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import GPUSlotWriteError, GPUSlotWriteFailure
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_recovery_failures import (
    GPURecoveryTargetConflictError,
    gpu_recovery_target_conflict_details,
)
from core.hardware.gpu_recovery_records import (
    GPUEffectState,
    GPUOriginalObservationState,
    GPURecoveryMember,
    GPURecoveryPhase,
    GPURecoveryRecord,
    GPURestorationState,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
    GPUVerificationState,
)
from core.types.json import JSONDict
from hardware.control.profiles import GPU_SLOT_FILE_VERSION
from hardware.gpu_tuning.control_recovery_serialization import (
    encode_recovery_record,
    recovery_scope_digest,
)
from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedGoal
from hardware.presets.slot_format import validate_gpu_slot_payload

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import (
        GPUControlReduction,
        GPUControlResult,
        GPUPreparedControl,
        GPUSlotReadResult,
    )
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.gpu_recovery_records import GPUControlMemberKey
    from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope

__all__ = (
    "create_observed_recovery_member",
    "create_prepared_recovery_record",
    "recovery_member_key",
    "require_application_targets",
    "require_record_target",
    "require_current_recovery_record",
    "require_plain_recovery_record",
    "require_uncommitted_startup_effect",
    "require_native_result_record",
    "require_startup_member_authority",
    "validate_prepared_record",
)


def recovery_member_key(member: GPURecoveryMember) -> GPUControlMemberKey:
    if member.backend is None:
        raise ValidationError("GPU recovery requires recorded member backend authority.")
    return member.backend, member.field, member.member_id, member.domain_id, member.pstate_id


def require_record_target(record: GPURecoveryRecord, target: GPUPhysicalDevice) -> None:
    expected, actual = record.physical_identity, target.identity
    expected_uuid = expected.uuid.casefold() if expected.uuid is not None else None
    actual_uuid = actual.uuid.casefold() if actual.uuid is not None else None
    expected_pci = (
        normalize_observed_full_pci_bdf(expected.pci_bdf_full)
        if expected.pci_bdf_full is not None
        else None
    )
    actual_pci = (
        normalize_observed_full_pci_bdf(actual.pci_bdf_full)
        if actual.pci_bdf_full is not None
        else None
    )
    identities_agree = (
        expected.native_device_path,
        expected_uuid,
        expected_pci,
        expected.windows_pnp_instance_id,
    ) == (actual.native_device_path, actual_uuid, actual_pci, actual.windows_pnp_instance_id)
    if (
        record.device_id != target.device_id
        or not identities_agree
        or record.pci_bdf_observations is None
        or record.pci_bdf_observations != target.pci_bdf_observations
    ):
        raise GPURecoveryTargetConflictError(
            "GPU recovery record conflicts with the current physical target.",
            details=gpu_recovery_target_conflict_details(
                record,
                target,
                expected_uuid=expected_uuid,
                actual_uuid=actual_uuid,
                expected_pci=expected_pci,
                actual_pci=actual_pci,
            ),
        )


def validate_prepared_record(record: GPURecoveryRecord, target: GPUPhysicalDevice) -> None:
    require_record_target(record, target)
    require_application_targets(record)
    if record.phase != GPURecoveryPhase.PREPARED or record.commit_intent is None:
        raise ValidationError("GPU preparation requires explicit frozen finalization authority.")
    validate_gpu_slot_payload(
        {
            "version": GPU_SLOT_FILE_VERSION,
            "devices": {},
            "recovery": {record.device_id: encode_recovery_record(record)},
        }
    )
    for member in record.members:
        recovery_member_key(member)
        if member.original_value is None and member.original_mode is None:
            raise ValidationError("GPU preparation requires an actual observed original.")
        if (
            member.original_observation != GPUOriginalObservationState.OBSERVED
            or member.effect != GPUEffectState.NOT_ATTEMPTED
            or member.changed is not False
            or member.verification != GPUVerificationState.NOT_ATTEMPTED
        ):
            raise ValidationError(
                "GPU preparation requires observed originals and zero prior effects."
            )


def require_application_targets(record: GPURecoveryRecord) -> None:
    if any(
        member.requested_value is None and member.requested_mode is None
        for member in record.members
    ):
        raise ValidationError("GPU application requires actual frozen native member targets.")


def require_plain_recovery_record(read: GPUSlotReadResult, device_id: str) -> GPURecoveryRecord:
    for record in read.recovery_records:
        if record.device_id == device_id:
            if isinstance(record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
                raise ValidationError(
                    "GPU startup recovery requires explicit whole-scope ownership."
                )
            return record
    raise ValidationError("GPU prepared record is missing.")


def require_current_recovery_record(
    read: GPUSlotReadResult, prepared: GPUPreparedControl
) -> GPURecoveryRecord:
    if read.revision != prepared.store_revision:
        raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
    selected = None
    for stored in read.recovery_records:
        if stored.device_id != prepared.target.device_id:
            continue
        if isinstance(stored, GPUStartupRecoveryRecord):
            for child in (stored.original_record, stored.legacy_record):
                if child.operation_id == prepared.operation_id:
                    selected = child
        elif isinstance(stored, GPUStartupLegacyRecoveryRecord):
            if stored.legacy_record.operation_id == prepared.operation_id:
                selected = stored.legacy_record
        else:
            selected = stored
    if selected is None:
        raise ValidationError("GPU prepared record or selected startup child is missing.")
    require_record_target(selected, prepared.target)
    if (
        selected.operation_id != prepared.operation_id
        or recovery_scope_digest(selected) != prepared.scope_digest
        or set(prepared.member_keys) != {recovery_member_key(member) for member in selected.members}
    ):
        raise ValidationError("GPU prepared scope no longer matches its frozen record.")
    return selected


def require_uncommitted_startup_effect(
    read: GPUSlotReadResult, prepared: GPUPreparedControl
) -> None:
    for stored in read.recovery_records:
        if (
            isinstance(stored, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord)
            and stored.device_id == prepared.target.device_id
            and stored.legacy_record.operation_id == prepared.operation_id
            and stored.legacy_commit is not None
        ):
            raise ValidationError("GPU committed startup legacy permits fresh verification only.")


def require_native_result_record(
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    result: GPUControlResult,
    reduction: GPUControlReduction,
) -> GPURecoveryRecord:
    updated = replace(
        record,
        members=tuple(member.recovery_member for member in result.members),
        phase=(
            GPURecoveryPhase.RECONCILING
            if record.phase == GPURecoveryPhase.RECONCILING
            else (
                GPURecoveryPhase.UNRESOLVED if reduction.unresolved else GPURecoveryPhase.PREPARED
            )
        ),
    )
    if recovery_scope_digest(updated) != prepared.scope_digest:
        raise ValidationError("GPU native result changed frozen originals or routing.")
    prior = {recovery_member_key(member): member for member in record.members}
    for member in updated.members:
        previous = prior[recovery_member_key(member)]
        if (
            previous.effect == GPUEffectState.NOT_ATTEMPTED
            and member.effect != GPUEffectState.NOT_ATTEMPTED
        ):
            raise ValidationError("GPU native invocation lacks a durable before-effect checkpoint.")
        if previous.changed is True and member.changed is not True:
            raise ValidationError("GPU native result discarded a known member effect.")
    return updated


def require_startup_member_authority(
    scope: GPUControlStartupScope | None,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    member_key: GPUControlMemberKey,
) -> None:
    if scope is None:
        raise ValidationError("GPU historical effects require active complete startup ownership.")
    matching = tuple(
        row for row in scope.recorded if row.record.operation_id == record.operation_id
    )
    if matching:
        if (
            len(matching) != 1
            or matching[0].state != GPUPhysicalBindingState.BOUND
            or matching[0].goal == GPUStartupRecordedGoal.COMMITTED_LEGACY_TARGET
        ):
            raise ValidationError("GPU startup goal does not authorize another effect.")
        frozen, target = matching[0].record, matching[0].target
    else:
        rows = (
            ()
            if scope.legacy_plan is None
            else tuple(
                row
                for row in scope.legacy_plan.devices
                if row.record is not None and row.record.operation_id == record.operation_id
            )
        )
        if len(rows) != 1 or rows[0].record is None or rows[0].rejection is not None:
            raise ValidationError("GPU startup effect has no actual selected legacy plan.")
        frozen, target = rows[0].record, rows[0].target
    if target != prepared.target or recovery_scope_digest(frozen) != prepared.scope_digest:
        raise ValidationError("GPU startup effect changed its physical or frozen native scope.")
    if member_key not in tuple(recovery_member_key(member) for member in frozen.members):
        raise ValidationError("GPU startup effect is outside its selected native goal.")


def create_observed_recovery_member(
    *,
    field: str,
    member_id: str,
    backend: str,
    native_unit: str,
    domain_id: int | None,
    pstate_id: int | None,
    original_value: int | float | None,
    original_mode: int | str | None,
    requested_value: int | float | None,
    requested_mode: int | str | None,
) -> GPURecoveryMember:
    return GPURecoveryMember(
        field=field,
        member_id=member_id,
        backend=backend,
        native_unit=native_unit,
        domain_id=domain_id,
        pstate_id=pstate_id,
        original_value=original_value,
        original_mode=original_mode,
        requested_value=requested_value,
        requested_mode=requested_mode,
        original_observation=GPUOriginalObservationState.OBSERVED,
        effect=GPUEffectState.NOT_ATTEMPTED,
        verification=GPUVerificationState.NOT_ATTEMPTED,
        restoration=GPURestorationState.NOT_REQUIRED,
        changed=False,
    )


def create_prepared_recovery_record(
    *,
    operation_id: str,
    target: GPUPhysicalDevice,
    backend: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
    requested_units: JSONDict,
    members: tuple[GPURecoveryMember, ...],
) -> GPURecoveryRecord:
    return GPURecoveryRecord(
        operation_id=operation_id,
        device_id=target.device_id,
        physical_identity=target.identity,
        backend=backend,
        phase=GPURecoveryPhase.PREPARED,
        requested_settings=requested_settings,
        requested_modes=requested_modes,
        requested_units=requested_units,
        members=members,
        pci_bdf_observations=target.pci_bdf_observations,
        commit_intent=None,
    )

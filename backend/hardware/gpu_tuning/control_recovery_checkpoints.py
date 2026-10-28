"""SoAI - Selected GPU recovery checkpoint CAS and actual receipt binding [backend/hardware/gpu_tuning/control_recovery_checkpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import (
    GPUPreparedControl,
    GPURecoveryAdmissionState,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_recovery_records import (
    GPUEffectState,
    GPUOriginalObservationState,
    GPURecoveryPhase,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
    GPUVerificationState,
)
from core.types.json_value import require_json_dict
from hardware.gpu_tuning.control_recovery_completion import inspect_recovery_admission
from hardware.gpu_tuning.control_recovery_records import (
    recovery_member_key,
    require_application_targets,
    require_current_recovery_record,
    require_plain_recovery_record,
    require_record_target,
    validate_prepared_record,
)
from hardware.gpu_tuning.control_recovery_serialization import (
    encode_recovery_record,
    recovery_scope_digest,
)
from hardware.gpu_tuning.control_saved_state_authority import require_saved_control_authority
from hardware.gpu_tuning.startup_scope_accounting import require_complete_startup_accounting
from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedGoal, GPUStartupScopePolicy

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import GPUControlDirtyMarkerReceipt, GPUSlotReadResult
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.gpu_recovery_records import GPUControlMemberKey, GPURecoveryRecord
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from hardware.gpu_tuning.control_recovery_completion import GPURecoveryPendingCommit
    from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope


__all__ = (
    "create_prepared_recovery",
    "resume_original_recovery_checkpoint",
    "resume_startup_recorded_goal",
    "resume_requested_control_receipt",
    "create_startup_legacy_recovery",
    "create_prepared_control_receipt",
    "persist_recovery_checkpoint",
    "persist_pending_effect_checkpoint",
)


def create_prepared_recovery(
    storage: GpuSlotStorageManagerProtocol,
    pending: dict[str, GPURecoveryPendingCommit],
    target: GPUPhysicalDevice,
    record: GPURecoveryRecord,
) -> GPUPreparedControl:
    record = copy.deepcopy(record)
    validate_prepared_record(record, target)
    return _persist_new_recovery_slot(storage, pending, target, record, record)


def resume_original_recovery_checkpoint(
    storage: GpuSlotStorageManagerProtocol, target: GPUPhysicalDevice
) -> GPUPreparedControl:
    with storage.lock:
        read = storage.read_payload()
        record = require_plain_recovery_record(read, target.device_id)
        require_record_target(record, target)
        _require_recorded_originals(record)
        prepared = create_prepared_control_receipt(target, record, read, None)
        return persist_recovery_checkpoint(
            storage, prepared, read, replace(record, phase=GPURecoveryPhase.RECONCILING)
        )


def resume_startup_recorded_goal(
    storage: GpuSlotStorageManagerProtocol,
    scope: GPUControlStartupScope,
    target: GPUPhysicalDevice,
    operation_id: str,
    goal: GPUStartupRecordedGoal,
) -> GPUPreparedControl:
    require_complete_startup_accounting(scope)
    rows = tuple(
        row
        for row in scope.recorded
        if row.record.operation_id == operation_id
        and row.goal == goal
        and row.target == target
        and row.state == GPUPhysicalBindingState.BOUND
    )
    if len(rows) != 1:
        raise ValidationError("GPU startup receipt requires its exact bound recorded goal.")
    record = copy.deepcopy(rows[0].record)
    with storage.lock:
        read = storage.read_payload()
        prepared = create_prepared_control_receipt(target, record, read, None)
        if goal == GPUStartupRecordedGoal.ORIGINAL:
            _require_recorded_originals(record)
            return persist_recovery_checkpoint(
                storage, prepared, read, replace(record, phase=GPURecoveryPhase.RECONCILING)
            )
        return prepared


def _require_recorded_originals(record: GPURecoveryRecord) -> None:
    if any(
        member.backend is None
        or member.original_observation != GPUOriginalObservationState.OBSERVED
        or (member.original_value is None and member.original_mode is None)
        for member in record.members
    ):
        raise ValidationError("GPU reconciliation requires complete recorded originals.")


def resume_requested_control_receipt(
    storage: GpuSlotStorageManagerProtocol, target: GPUPhysicalDevice
) -> GPUPreparedControl:
    with storage.lock:
        read = storage.read_payload()
        record = require_plain_recovery_record(read, target.device_id)
        require_record_target(record, target)
        require_application_targets(record)
        if record.commit_intent is None or any(member.backend is None for member in record.members):
            raise ValidationError("Historical GPU recovery lacks recorded replay authority.")
        return create_prepared_control_receipt(target, record, read, None)


def create_startup_legacy_recovery(
    storage: GpuSlotStorageManagerProtocol,
    pending: dict[str, GPURecoveryPendingCommit],
    scope: GPUControlStartupScope,
    target: GPUPhysicalDevice,
    record: GPURecoveryRecord,
    startup_operation_id: str,
) -> GPUPreparedControl:
    record = copy.deepcopy(record)
    validate_prepared_record(record, target)
    if scope.policy != GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL or scope.legacy_plan is None:
        raise ValidationError("GPU legacy preparation requires its historical startup scope.")
    selected = tuple(
        plan
        for plan in scope.legacy_plan.devices
        if plan.target == target and plan.record == record and plan.rejection is None
    )
    if len(selected) != 1:
        raise ValidationError("GPU legacy preparation differs from its frozen startup plan.")
    outer = GPUStartupLegacyRecoveryRecord(startup_operation_id, record.device_id, record, None)
    return _persist_new_recovery_slot(storage, pending, target, record, outer)


def _persist_new_recovery_slot(
    storage: GpuSlotStorageManagerProtocol,
    pending: dict[str, GPURecoveryPendingCommit],
    target: GPUPhysicalDevice,
    selected: GPURecoveryRecord,
    outer: GPURecoveryRecord | GPUStartupLegacyRecoveryRecord,
) -> GPUPreparedControl:
    with storage.lock:
        read = storage.read_payload()
        if (
            inspect_recovery_admission(target, read, pending).state
            != GPURecoveryAdmissionState.CLEAR
        ):
            raise ValidationError("GPU unresolved recovery blocks new mutation.")
        require_saved_control_authority(read.payload, selected)
        payload = copy.deepcopy(read.payload)
        recovery = require_json_dict(payload.get("recovery"), label="GPU recovery")
        recovery[target.device_id] = encode_recovery_record(outer)
        payload["recovery"] = recovery
        storage.write_payload(payload, expected_read=read)
        return create_prepared_control_receipt(target, selected, storage.read_payload(), None)


def create_prepared_control_receipt(
    target: GPUPhysicalDevice,
    record: GPURecoveryRecord,
    read: GPUSlotReadResult,
    dirty_marker_receipt: GPUControlDirtyMarkerReceipt | None,
) -> GPUPreparedControl:
    if read.revision is None:
        raise ValidationError("GPU durable preparation requires an actual store revision.")
    prepared = GPUPreparedControl(
        operation_id=record.operation_id,
        target=target,
        member_keys=tuple(recovery_member_key(member) for member in record.members),
        scope_digest=recovery_scope_digest(record),
        store_revision=read.revision,
        dirty_marker_receipt=dirty_marker_receipt,
    )
    if require_current_recovery_record(read, prepared) != record:
        raise ValidationError("GPU receipt requires its complete actual durable record.")
    return prepared


def persist_recovery_checkpoint(
    storage: GpuSlotStorageManagerProtocol,
    prepared: GPUPreparedControl,
    read: GPUSlotReadResult,
    record: GPURecoveryRecord,
) -> GPUPreparedControl:
    record, read = copy.deepcopy(record), copy.deepcopy(read)
    selected = require_current_recovery_record(read, prepared)
    require_record_target(record, prepared.target)
    if record.operation_id != prepared.operation_id or (
        recovery_scope_digest(record) != prepared.scope_digest
    ):
        raise ValidationError("GPU checkpoint changed its frozen selected scope.")
    if record == selected:
        if storage.read_payload() != read:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        return prepared
    payload = copy.deepcopy(read.payload)
    recovery = require_json_dict(payload.get("recovery"), label="GPU recovery")
    stored = next(item for item in read.recovery_records if item.device_id == record.device_id)
    if isinstance(stored, GPUStartupRecoveryRecord):
        if stored.original_record.operation_id == record.operation_id:
            stored = replace(stored, original_record=record)
        elif stored.legacy_record.operation_id == record.operation_id:
            stored = replace(stored, legacy_record=record)
        else:
            raise ValidationError("GPU checkpoint does not select a recorded startup child.")
    elif isinstance(stored, GPUStartupLegacyRecoveryRecord):
        if stored.legacy_record.operation_id != record.operation_id:
            raise ValidationError("GPU checkpoint does not select its recorded legacy child.")
        stored = replace(stored, legacy_record=record)
    else:
        stored = record
    recovery[record.device_id] = encode_recovery_record(stored)
    payload["recovery"] = recovery
    storage.write_payload(payload, expected_read=read)
    return create_prepared_control_receipt(
        prepared.target, record, storage.read_payload(), prepared.dirty_marker_receipt
    )


def persist_pending_effect_checkpoint(
    storage: GpuSlotStorageManagerProtocol,
    prepared: GPUPreparedControl,
    read: GPUSlotReadResult,
    record: GPURecoveryRecord,
    member_key: GPUControlMemberKey,
) -> GPUPreparedControl:
    if member_key not in prepared.member_keys:
        raise ValidationError("GPU effect is outside prepared member authority.")
    members = tuple(
        (
            replace(
                member,
                effect=GPUEffectState.ATTEMPTED_UNKNOWN,
                changed=True if member.changed is True else None,
                verification=GPUVerificationState.NOT_ATTEMPTED,
            )
            if recovery_member_key(member) == member_key
            else member
        )
        for member in record.members
    )
    updated = replace(
        record,
        members=members,
        phase=(
            GPURecoveryPhase.RECONCILING
            if record.phase == GPURecoveryPhase.RECONCILING
            else GPURecoveryPhase.UNRESOLVED
        ),
    )
    return persist_recovery_checkpoint(storage, prepared, read, updated)

"""SoAI - Atomic GPU completion and exact durability reconciliation [backend/hardware/gpu_tuning/control_recovery_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.path_coercion import coerce_path
from core.hardware.gpu_control_types import (
    GPUControlCommitAcknowledgement,
    GPURecoveryAdmissionState,
    GPUSlotReadError,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.hardware.gpu_recovery_records import (
    GPUOriginalObservationState,
    GPURecoveryPhase,
    GPURestorationState,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.timing.formatting import utc_now_iso
from core.types.json_value import require_json_dict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.control_recovery_admission import inspect_recovery_records
from hardware.gpu_tuning.control_recovery_records import (
    recovery_member_key,
    require_record_target,
)
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.control_saved_state_authority import (
    apply_verified_user_state,
    require_saved_control_authority,
)
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.presets.slot_format import decode_gpu_slot_payload
from hardware.presets.slot_storage import serialize_gpu_slot_write_bytes

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import (
        GPUControlReduction,
        GPUControlResult,
        GPUPreparedControl,
        GPURecoveryAdmission,
        GPUSlotReadResult,
    )
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.gpu_recovery_records import GPURecoveryRecord
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.startup_scope_types import GPUControlStartupVerification


__all__ = (
    "GPUStartupPendingAuthority",
    "GPURecoveryPendingCommit",
    "inspect_recovery_admission",
    "complete_requested_recovery",
    "complete_original_recovery",
    "require_original_recovery_readback",
    "require_complete_recovery_checkpoint",
    "reconcile_pending_commit",
    "require_pending_recovery_authority",
    "require_pending_prepared_authority",
)


@dataclass(frozen=True, slots=True)
class GPUStartupPendingAuthority:
    verification: GPUControlStartupVerification
    final_read: GPUSlotReadResult


@dataclass(frozen=True, slots=True)
class GPURecoveryPendingCommit:
    prepared: GPUPreparedControl
    record: GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord
    result: GPUControlResult
    candidate_bytes: bytes
    candidate_revision: str
    committed_at: str | None
    startup_authority: GPUStartupPendingAuthority | None


def inspect_recovery_admission(
    target: GPUPhysicalDevice, read: GPUSlotReadResult, pending: dict[str, GPURecoveryPendingCommit]
) -> GPURecoveryAdmission:
    records = list(read.recovery_records)
    for candidate in pending.values():
        if not any(
            record.device_id == candidate.record.device_id
            and recovery_scope_digest(record) == recovery_scope_digest(candidate.record)
            for record in records
        ):
            records.append(candidate.record)
    return inspect_recovery_records(target, tuple(records))


def complete_requested_recovery(
    storage: GpuSlotStorageManagerProtocol,
    pending: dict[str, GPURecoveryPendingCommit],
    prepared: GPUPreparedControl,
    read: GPUSlotReadResult,
    record: GPURecoveryRecord,
    result: GPUControlResult,
) -> GPUControlCommitAcknowledgement | None:
    reduction = reduce_gpu_control_result(result, prepared=prepared)
    if reduction.unresolved:
        raise ValidationError("GPU unresolved native outcome cannot complete recovery.")
    require_complete_recovery_checkpoint(record, result)
    if record.commit_intent is None:
        raise ValidationError("GPU completion lacks recorded user finalization authority.")
    payload = copy.deepcopy(read.payload)
    completed_at: str | None = None
    if reduction.persistence_eligible:
        require_saved_control_authority(payload, record)
        completed_at = utc_now_iso()
        apply_verified_user_state(payload, record, completed_at)
    elif reduction.changed is not False:
        raise ValidationError("GPU failed effects require explicit reconciliation.")
    return _commit_completion(
        storage, pending, prepared, read, record, result, payload, completed_at
    )


def complete_original_recovery(
    storage: GpuSlotStorageManagerProtocol,
    pending: dict[str, GPURecoveryPendingCommit],
    prepared: GPUPreparedControl,
    read: GPUSlotReadResult,
    record: GPURecoveryRecord,
    result: GPUControlResult,
) -> None:
    reduce_gpu_control_result(result, prepared=prepared)
    require_complete_recovery_checkpoint(record, result)
    require_original_recovery_readback(record, result)
    _commit_completion(
        storage, pending, prepared, read, record, result, copy.deepcopy(read.payload), None
    )


def require_original_recovery_readback(record: GPURecoveryRecord, result: GPUControlResult) -> None:
    if record.phase != GPURecoveryPhase.RECONCILING:
        raise ValidationError("GPU original-state completion requires reconciliation authority.")
    for outcome in result.members:
        member = outcome.recovery_member
        if member.original_value is None and member.original_mode is None:
            raise ValidationError("GPU reconciliation original state is unavailable.")
        if member.original_observation != GPUOriginalObservationState.OBSERVED:
            raise ValidationError("GPU reconciliation requires actual original evidence.")
        if (
            member.restoration
            not in (GPURestorationState.RESTORED, GPURestorationState.NOT_REQUIRED)
            or (
                member.original_value is not None
                and member.original_value != outcome.observed_value
            )
            or (member.original_mode is not None and member.original_mode != outcome.observed_mode)
        ):
            raise ValidationError("GPU reconciliation lacks matching actual original readback.")


def require_complete_recovery_checkpoint(
    record: GPURecoveryRecord, result: GPUControlResult
) -> None:
    members = {recovery_member_key(member): member for member in record.members}
    if any(
        members[recovery_member_key(member.recovery_member)] != member.recovery_member
        for member in result.members
    ):
        raise ValidationError("GPU completion requires its durable complete result checkpoint.")


def _commit_completion(
    storage: GpuSlotStorageManagerProtocol,
    pending: dict[str, GPURecoveryPendingCommit],
    prepared: GPUPreparedControl,
    read: GPUSlotReadResult,
    record: GPURecoveryRecord,
    result: GPUControlResult,
    payload: JSONDict,
    completed_at: str | None,
) -> GPUControlCommitAcknowledgement | None:
    if record.device_id in pending:
        raise ValidationError("GPU pending durability requires explicit reconciliation.")
    recovery = require_json_dict(payload.get("recovery"), label="GPU recovery")
    del recovery[record.device_id]
    payload["recovery"] = recovery
    candidate_bytes = serialize_gpu_slot_write_bytes(payload)
    candidate = GPURecoveryPendingCommit(
        prepared,
        copy.deepcopy(record),
        copy.deepcopy(result),
        candidate_bytes,
        hashlib.sha256(candidate_bytes).hexdigest(),
        completed_at,
        None,
    )
    pending[record.device_id] = candidate
    try:
        storage.write_payload(payload, expected_read=read)
    except GPUSlotReadError:
        del pending[record.device_id]
        raise
    except GPUSlotWriteError as exception:
        if exception.reason != GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN:
            del pending[record.device_id]
        raise
    committed = storage.read_payload()
    if committed.revision != candidate.candidate_revision:
        raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
    acknowledgement = _acknowledgement(candidate, candidate.candidate_revision)
    del pending[record.device_id]
    return acknowledgement


def reconcile_pending_commit(
    storage: GpuSlotStorageManagerProtocol,
    pending: dict[str, GPURecoveryPendingCommit],
    prepared: GPUPreparedControl,
    dirty_flag_path: str,
) -> GPUControlCommitAcknowledgement | None:
    candidate, reduction = require_pending_recovery_authority(pending, prepared, dirty_flag_path)
    if isinstance(candidate.record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
        raise ValidationError("GPU startup durability requires its whole-scope completion owner.")
    read = storage.read_payload()
    if read.revision is None:
        raise GPUSlotWriteError(GPUSlotWriteFailure.UNAVAILABLE)
    if read.revision != candidate.candidate_revision:
        preserved = decode_gpu_slot_payload(candidate.candidate_bytes)
        candidate_devices = require_json_dict(
            preserved.payload.get("devices"), label="GPU candidate devices"
        )
        current_devices = require_json_dict(
            read.payload.get("devices"), label="GPU current devices"
        )
        device_id = prepared.target.device_id
        if device_id in candidate_devices:
            expected_entry = candidate_devices[device_id]
            current_entry = current_devices.get(device_id)
            if (
                not isinstance(expected_entry, dict)
                or not isinstance(current_entry, dict)
                or expected_entry != current_entry
            ):
                raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        else:
            if device_id in current_devices or candidate.committed_at is not None:
                raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
            if candidate.record.phase == GPURecoveryPhase.RECONCILING:
                require_original_recovery_readback(candidate.record, candidate.result)
            elif (
                reduction.changed is not False
                or reduction.unresolved
                or reduction.persistence_eligible
            ):
                raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        if (
            inspect_recovery_records(prepared.target, read.recovery_records).state
            != GPURecoveryAdmissionState.CLEAR
        ):
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
    storage.synchronize_revision(expected_revision=read.revision)
    acknowledgement = _acknowledgement(replace(candidate, prepared=prepared), read.revision)
    del pending[prepared.target.device_id]
    return acknowledgement


def require_pending_recovery_authority(
    pending: dict[str, GPURecoveryPendingCommit], prepared: GPUPreparedControl, dirty_flag_path: str
) -> tuple[GPURecoveryPendingCommit, GPUControlReduction]:
    candidate = require_pending_prepared_authority(pending, prepared, dirty_flag_path)
    if isinstance(candidate.record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
        raise ValidationError("GPU startup durability requires its whole-scope completion owner.")
    require_record_target(candidate.record, prepared.target)
    if recovery_scope_digest(candidate.record) != prepared.scope_digest:
        raise ValidationError("GPU pending durability scope changed.")
    return candidate, reduce_gpu_control_result(candidate.result, prepared=prepared)


def require_pending_prepared_authority(
    pending: dict[str, GPURecoveryPendingCommit], prepared: GPUPreparedControl, dirty_flag_path: str
) -> GPURecoveryPendingCommit:
    require_canonical_trimmed_json_text(
        dirty_flag_path, error_message="GPU dirty marker path is invalid."
    )
    coerce_path(dirty_flag_path)
    candidate = pending.get(prepared.target.device_id)
    if candidate is None or not _essential_prepared_authority_matches(candidate.prepared, prepared):
        raise ValidationError("GPU durability reconciliation requires its exact pending authority.")
    if candidate.startup_authority is not None:
        raise ValidationError("GPU startup durability requires its whole-scope completion owner.")
    for receipt in (candidate.prepared, prepared):
        if (
            receipt.dirty_marker_receipt is not None
            and receipt.dirty_marker_receipt.marker_path != dirty_flag_path
        ):
            raise ValidationError("GPU pending marker receipt belongs to another authority.")
    return candidate


def _essential_prepared_authority_matches(
    recorded: GPUPreparedControl, supplied: GPUPreparedControl
) -> bool:
    return (
        recorded.operation_id == supplied.operation_id
        and recorded.target == supplied.target
        and recorded.member_keys == supplied.member_keys
        and recorded.scope_digest == supplied.scope_digest
        and recorded.store_revision == supplied.store_revision
    )


def _acknowledgement(
    candidate: GPURecoveryPendingCommit, committed_revision: str
) -> GPUControlCommitAcknowledgement | None:
    if candidate.committed_at is None:
        return None
    if isinstance(candidate.record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
        raise ValidationError("GPU startup user acknowledgement requires its legacy commit owner.")
    intent = candidate.record.commit_intent
    if intent is None:
        raise ValidationError("GPU user acknowledgement requires its frozen commit intent.")
    return GPUControlCommitAcknowledgement(
        candidate.prepared, intent, committed_revision, candidate.committed_at
    )

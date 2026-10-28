"""SoAI - Retained startup legacy user-state commit authority [backend/hardware/gpu_tuning/startup_reconciliation_authority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import (
    GPUControlCommitAcknowledgement,
    GPUSlotReadError,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.hardware.gpu_recovery_records import (
    GPUStartupLegacyCommit,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.timing.formatting import utc_now_iso
from core.types.json_value import require_json_dict
from hardware.gpu_tuning.control_recovery_checkpoints import create_prepared_control_receipt
from hardware.gpu_tuning.control_recovery_completion import (
    GPURecoveryPendingCommit,
    require_complete_recovery_checkpoint,
    require_pending_prepared_authority,
)
from hardware.gpu_tuning.control_recovery_records import (
    require_current_recovery_record,
)
from hardware.gpu_tuning.control_recovery_serialization import encode_recovery_record
from hardware.gpu_tuning.control_saved_state_authority import (
    apply_verified_user_state,
    control_state_digest,
    require_saved_control_authority,
)
from hardware.gpu_tuning.dirty_shutdown_flag import establish_gpu_dirty_marker_receipt
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.native_startup_reconciliation import validate_startup_record_promotion
from hardware.gpu_tuning.startup_scope_accounting import require_complete_startup_accounting
from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedGoal, GPUStartupScopePolicy
from hardware.presets.slot_format import decode_gpu_slot_payload
from hardware.presets.slot_storage import serialize_gpu_slot_write_bytes

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import (
        GPUControlResult,
        GPUPreparedControl,
        GPUSlotReadResult,
    )
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from hardware.gpu_tuning.service_dependencies import GPUStartupAcquisitionResources
    from hardware.gpu_tuning.startup_scope_types import (
        GPUControlStartupScope,
        GPUStartupPromotionProof,
    )


__all__ = (
    "commit_startup_legacy_state",
    "reconcile_startup_legacy_state",
    "promote_startup_recovery",
)


def commit_startup_legacy_state(
    storage: GpuSlotStorageManagerProtocol,
    *,
    pending: dict[str, GPURecoveryPendingCommit],
    record: GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord,
    prepared: GPUPreparedControl,
    result: GPUControlResult,
) -> GPUControlCommitAcknowledgement | None:
    owned_record, owned_result = copy.deepcopy(record), copy.deepcopy(result)
    if not isinstance(owned_record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
        raise ValidationError("GPU startup user commit requires its complete retained slot.")
    with storage.lock:
        if owned_record.device_id in pending:
            raise ValidationError("GPU pending durability requires explicit reconciliation.")
        read = storage.read_payload()
        selected = require_current_recovery_record(read, prepared)
        retained = next(
            (entry for entry in read.recovery_records if entry.device_id == owned_record.device_id),
            None,
        )
        if retained != owned_record or selected != owned_record.legacy_record:
            raise ValidationError(
                "GPU startup user commit does not match its retained legacy scope."
            )
        reduction = reduce_gpu_control_result(owned_result, prepared=prepared)
        require_complete_recovery_checkpoint(selected, owned_result)
        if not reduction.persistence_eligible:
            raise ValidationError("GPU startup user commit requires complete native target proof.")
        if owned_record.legacy_commit is not None:
            if control_state_digest(read.payload, owned_record.device_id) != (
                owned_record.legacy_commit.completed_control_state_digest
            ):
                raise ValidationError("GPU committed startup saved authority changed.")
            return None
        require_saved_control_authority(read.payload, selected)
        completed_at = utc_now_iso()
        payload = copy.deepcopy(read.payload)
        apply_verified_user_state(payload, selected, completed_at)
        completed = replace(
            owned_record,
            legacy_commit=GPUStartupLegacyCommit(
                completed_at, control_state_digest(payload, owned_record.device_id)
            ),
        )
        recovery = require_json_dict(payload.get("recovery"), label="GPU startup recovery")
        recovery[owned_record.device_id] = encode_recovery_record(completed)
        payload["recovery"] = recovery
        candidate_bytes = serialize_gpu_slot_write_bytes(payload)
        candidate = GPURecoveryPendingCommit(
            prepared,
            owned_record,
            owned_result,
            candidate_bytes,
            hashlib.sha256(candidate_bytes).hexdigest(),
            completed_at,
            None,
        )
        pending[owned_record.device_id] = candidate
        try:
            storage.write_payload(payload, expected_read=read)
        except GPUSlotReadError:
            del pending[owned_record.device_id]
            raise
        except GPUSlotWriteError as exception:
            if exception.reason != GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN:
                del pending[owned_record.device_id]
            raise
        committed = storage.read_payload()
        if committed.revision != candidate.candidate_revision:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        intent = selected.commit_intent
        if intent is None:
            raise ValidationError("GPU startup user commit lacks its frozen intent.")
        acknowledgement = GPUControlCommitAcknowledgement(
            prepared, intent, candidate.candidate_revision, completed_at
        )
        del pending[owned_record.device_id]
        return acknowledgement


def reconcile_startup_legacy_state(
    storage: GpuSlotStorageManagerProtocol,
    *,
    pending: dict[str, GPURecoveryPendingCommit],
    prepared: GPUPreparedControl,
    dirty_flag_path: str,
) -> GPUControlCommitAcknowledgement:
    with storage.lock:
        retained = require_pending_prepared_authority(pending, prepared, dirty_flag_path)
        candidate = copy.deepcopy(retained)
        if not isinstance(
            candidate.record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord
        ):
            raise ValidationError("GPU legacy durability requires its retained startup slot.")
        if candidate.record.legacy_commit is not None or candidate.committed_at is None:
            raise ValidationError("GPU legacy durability requires its exact intermediate commit.")
        legacy = candidate.record.legacy_record
        original = replace(
            decode_gpu_slot_payload(candidate.candidate_bytes), revision=prepared.store_revision
        )
        selected = require_current_recovery_record(original, prepared)
        if selected != legacy:
            raise ValidationError("GPU legacy durability changed its frozen child scope.")
        require_complete_recovery_checkpoint(legacy, candidate.result)
        reduction = reduce_gpu_control_result(candidate.result, prepared=prepared)
        if not reduction.persistence_eligible or legacy.commit_intent is None:
            raise ValidationError("GPU legacy durability requires complete native target proof.")
        if hashlib.sha256(candidate.candidate_bytes).hexdigest() != candidate.candidate_revision:
            raise ValidationError("GPU legacy durability candidate bytes changed.")
        expected = replace(
            candidate.record,
            legacy_commit=GPUStartupLegacyCommit(
                candidate.committed_at, control_state_digest(original.payload, legacy.device_id)
            ),
        )
        stored = next(
            (
                record
                for record in original.recovery_records
                if record.device_id == legacy.device_id
            ),
            None,
        )
        if stored != expected:
            raise ValidationError("GPU legacy durability changed its full retained startup slot.")
        read = storage.read_payload()
        if read.revision is None:
            raise GPUSlotWriteError(GPUSlotWriteFailure.UNAVAILABLE)
        if read.revision != candidate.candidate_revision or read.payload != original.payload:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        if reduction.changed is not False or reduction.unresolved:
            prepared = replace(
                prepared,
                dirty_marker_receipt=establish_gpu_dirty_marker_receipt(
                    dirty_flag_path, prepared.dirty_marker_receipt
                ),
            )
        storage.synchronize_revision(expected_revision=candidate.candidate_revision)
        if pending.get(legacy.device_id) is not retained:
            raise ValidationError("GPU legacy durability pending owner changed.")
        acknowledgement = GPUControlCommitAcknowledgement(
            prepared, legacy.commit_intent, candidate.candidate_revision, candidate.committed_at
        )
        del pending[legacy.device_id]
        return acknowledgement


def promote_startup_recovery(
    storage: GpuSlotStorageManagerProtocol,
    *,
    pending: dict[str, GPURecoveryPendingCommit],
    scope: GPUControlStartupScope,
    target: GPUPhysicalDevice,
    record: GPUStartupRecoveryRecord,
    expected_read: GPUSlotReadResult,
    proof: GPUStartupPromotionProof,
    resources: GPUStartupAcquisitionResources,
) -> GPUPreparedControl:
    record, scope, expected_read, proof = copy.deepcopy((record, scope, expected_read, proof))
    require_complete_startup_accounting(scope)
    if (
        scope.policy != GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL
        or record.legacy_commit is not None
    ):
        raise ValidationError("GPU promotion requires its uncommitted historical scope.")
    originals = tuple(
        row
        for row in scope.recorded
        if row.goal == GPUStartupRecordedGoal.ORIGINAL
        and row.record.operation_id == record.original_record.operation_id
        and row.target == target
    )
    legacy = (
        tuple(
            row
            for row in scope.legacy_plan.devices
            if row.record == record.legacy_record and row.target == target
        )
        if scope.legacy_plan is not None
        else ()
    )
    if len(originals) != 1 or len(legacy) != 1 or originals[0].record != record.original_record:
        raise ValidationError("GPU promotion changed its complete initial original/legacy scope.")
    validate_startup_record_promotion(
        proof,
        record.original_record,
        record.legacy_record,
        target=target,
        executor=resources.executor,
        logger=resources.logger,
        gpu_services=resources.gpu_services,
        runtime_platform=resources.gpu_services.nvidia_nvml_gate.runtime_platform,
        acquisition_id=proof.acquisition_id,
        intel_executable=resources.gpu_services.intel_executable,
    )
    with storage.lock:
        if pending:
            raise ValidationError("GPU promotion conflicts with pending durable authority.")
        read = storage.read_payload()
        if read != expected_read:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        current = tuple(
            entry for entry in read.recovery_records if entry.device_id == record.device_id
        )
        if current != (record.original_record,):
            raise ValidationError("GPU promotion cannot replace changed original authority.")
        require_saved_control_authority(read.payload, record.legacy_record)
        payload = copy.deepcopy(read.payload)
        recovery = require_json_dict(payload.get("recovery"), label="GPU startup recovery")
        recovery[record.device_id] = encode_recovery_record(record)
        payload["recovery"] = recovery
        storage.write_payload(payload, expected_read=read)
        committed = storage.read_payload()
        stored = tuple(
            entry for entry in committed.recovery_records if entry.device_id == record.device_id
        )
        if stored != (record,):
            raise ValidationError("GPU promotion lost its complete retained startup slot.")
        return create_prepared_control_receipt(target, record.legacy_record, committed, None)

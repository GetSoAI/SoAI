"""SoAI - Whole startup recovery final transaction and exact durability repair [backend/hardware/gpu_tuning/startup_recovery_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import GPUSlotReadError, GPUSlotWriteError, GPUSlotWriteFailure
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalBindingState
from core.hardware.gpu_recovery_records import (
    GPUOriginalObservationState,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.types.json_value import require_json_dict
from core.validation.booleans import parse_bool
from hardware.gpu_tuning.control_recovery_completion import (
    GPURecoveryPendingCommit,
    GPUStartupPendingAuthority,
    require_complete_recovery_checkpoint,
    require_original_recovery_readback,
)
from hardware.gpu_tuning.control_recovery_records import require_current_recovery_record
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.control_saved_state_authority import control_state_digest
from hardware.gpu_tuning.dirty_shutdown_flag import remove_gpu_startup_marker
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.startup_route_applicability import require_applicable_startup_routes
from hardware.gpu_tuning.startup_scope_accounting import require_complete_startup_accounting
from hardware.gpu_tuning.startup_scope_types import (
    GPUControlStartupVerification,
    GPUStartupRecordedGoal,
    GPUStartupScopePolicy,
)
from hardware.presets.slot_storage import serialize_gpu_slot_write_bytes

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import GPUSlotReadResult
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from core.types.json import JSONDict


__all__ = (
    "commit_startup_boot_disablement",
    "complete_startup_recovery",
    "reconcile_startup_recovery",
    "require_startup_completion_evidence",
)


def commit_startup_boot_disablement(
    storage: GpuSlotStorageManagerProtocol,
    *,
    initial_read: GPUSlotReadResult,
    verification: GPUControlStartupVerification,
) -> tuple[GPUSlotReadResult, dict[str, JSONDict]]:
    initial_read, verification = copy.deepcopy((initial_read, verification))
    if verification.scope.policy != GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
        raise ValidationError("GPU historical boot disable requires its complete startup scope.")
    with storage.lock:
        read = storage.read_payload()
        require_startup_completion_evidence(verification, read)
        _require_saved_projections(initial_read, read, verification.scope.policy)
        payload = copy.deepcopy(read.payload)
        devices = require_json_dict(payload.get("devices"), label="GPU startup devices")
        affected: dict[str, JSONDict] = {}
        for device_id, value in devices.items():
            if not isinstance(value, dict):
                raise ValidationError("GPU startup saved device authority is invalid.")
            boot = value.get("boot")
            if isinstance(boot, dict) and parse_bool(boot.get("enabled"), default=False):
                boot["enabled"] = False
                affected[device_id] = copy.deepcopy(value)
        if affected:
            expected_revision = hashlib.sha256(serialize_gpu_slot_write_bytes(payload)).hexdigest()
            storage.write_payload(payload, expected_read=read)
        elif read.revision is not None:
            expected_revision = read.revision
            storage.synchronize_revision(expected_revision=read.revision)
        else:
            raise GPUSlotWriteError(GPUSlotWriteFailure.UNAVAILABLE)
        final = storage.read_payload()
        if final.payload != payload or final.revision != expected_revision:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        return final, affected


def complete_startup_recovery(
    storage: GpuSlotStorageManagerProtocol,
    *,
    pending: dict[str, GPURecoveryPendingCommit],
    initial_read: GPUSlotReadResult,
    verification: GPUControlStartupVerification,
    dirty_flag_path: str,
) -> GPUSlotReadResult:
    verification, initial_read = copy.deepcopy((verification, initial_read))
    with storage.lock:
        if pending:
            raise ValidationError(
                "GPU startup closure requires the complete pending union cleared."
            )
        read = storage.read_payload()
        require_startup_completion_evidence(verification, read)
        if initial_read.recovery_records != verification.scope.initial_records:
            raise ValidationError("GPU startup initial saved scope differs from native accounting.")
        _require_saved_projections(initial_read, read, verification.scope.policy)
        if read.revision is None:
            raise GPUSlotWriteError(GPUSlotWriteFailure.UNAVAILABLE)
        storage.synchronize_revision(expected_revision=read.revision)
        remove_gpu_startup_marker(dirty_flag_path)
        if not read.recovery_records:
            final = storage.read_payload()
            if final != read:
                raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
            return final
        payload = _completed_payload(read)
        candidate_bytes = serialize_gpu_slot_write_bytes(payload)
        revision = hashlib.sha256(candidate_bytes).hexdigest()
        authority = GPUStartupPendingAuthority(verification, read)
        rows = verification.recorded_readbacks + verification.legacy_readbacks
        for record in read.recovery_records:
            child = (
                record.original_record
                if isinstance(record, GPUStartupRecoveryRecord)
                else (
                    record.legacy_record
                    if isinstance(record, GPUStartupLegacyRecoveryRecord)
                    else record
                )
            )
            row = next(item for item in rows if item.record.operation_id == child.operation_id)
            pending[record.device_id] = GPURecoveryPendingCommit(
                row.prepared, record, row.result, candidate_bytes, revision, None, authority
            )
        try:
            storage.write_payload(payload, expected_read=read)
        except GPUSlotReadError:
            _discard_registered(pending, authority)
            raise
        except GPUSlotWriteError as exception:
            if exception.reason != GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN:
                _discard_registered(pending, authority)
            raise
        final = storage.read_payload()
        if final.revision != revision or final.payload != payload:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        _discard_registered(pending, authority)
        return final


def reconcile_startup_recovery(
    storage: GpuSlotStorageManagerProtocol,
    *,
    pending: dict[str, GPURecoveryPendingCommit],
    verification: GPUControlStartupVerification,
) -> GPUSlotReadResult:
    verification = copy.deepcopy(verification)
    with storage.lock:
        candidates = tuple(pending.values())
        if not candidates:
            raise ValidationError("GPU startup durability requires its retained aggregate.")
        first = candidates[0]
        authority = first.startup_authority
        if authority is None or authority.verification != verification:
            raise ValidationError("GPU startup durability changed its actual verification.")
        require_startup_completion_evidence(verification, authority.final_read)
        payload = _completed_payload(authority.final_read)
        expected_bytes = serialize_gpu_slot_write_bytes(payload)
        expected_revision = hashlib.sha256(expected_bytes).hexdigest()
        expected_devices = {record.device_id for record in authority.final_read.recovery_records}
        if set(pending) != expected_devices:
            raise ValidationError("GPU startup durability changed its complete pending union.")
        for device_id, candidate in pending.items():
            exact_aggregate_bytes = (
                candidate.candidate_bytes == expected_bytes
                and candidate.candidate_revision == expected_revision
            )
            if (
                device_id != candidate.record.device_id
                or candidate.startup_authority != authority
                or not exact_aggregate_bytes
                or candidate.committed_at is not None
                or candidate.record not in authority.final_read.recovery_records
            ):
                raise ValidationError("GPU startup durability changed its retained candidate.")
            rows = verification.recorded_readbacks + verification.legacy_readbacks
            if not any(
                row.prepared == candidate.prepared and row.result == candidate.result
                for row in rows
            ):
                raise ValidationError("GPU startup durability changed its actual native witness.")
            selected = require_current_recovery_record(
                replace(authority.final_read, revision=candidate.prepared.store_revision),
                candidate.prepared,
            )
            require_complete_recovery_checkpoint(selected, candidate.result)
            reduce_gpu_control_result(candidate.result, prepared=candidate.prepared)
        read = storage.read_payload()
        if read.revision != expected_revision or read.payload != payload:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        storage.synchronize_revision(expected_revision=expected_revision)
        final = storage.read_payload()
        if final != read:
            raise GPUSlotWriteError(GPUSlotWriteFailure.REVISION_CONFLICT)
        _discard_registered(pending, authority)
        return final


def require_startup_completion_evidence(
    verification: GPUControlStartupVerification, read: GPUSlotReadResult
) -> None:
    if not isinstance(verification, GPUControlStartupVerification):
        raise ValidationError("GPU startup completion requires actual native verification.")
    scope = verification.scope
    require_complete_startup_accounting(scope)
    if any(row.state != GPUPhysicalBindingState.BOUND for row in scope.recorded):
        raise ValidationError("GPU startup completion retains an unavailable recorded original.")
    if scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
        if any(
            vendor.state != GPUInventoryReadState.OBSERVED
            for vendor in verification.physical_snapshot.vendors
        ):
            raise ValidationError(
                "GPU startup completion retains unavailable physical acquisition."
            )
        if scope.legacy_plan is None:
            if any(
                roster.state != GPUInventoryReadState.OBSERVED for roster in verification.rosters
            ):
                raise ValidationError(
                    "GPU startup completion retains unavailable native acquisition."
                )
        else:
            require_applicable_startup_routes(
                verification.rosters,
                plan=scope.legacy_plan,
                initial_records=scope.initial_records,
                message="GPU startup completion retains unavailable native acquisition.",
            )
        if any(
            facility.state == GPUOriginalObservationState.UNAVAILABLE
            for facility in verification.facilities
        ):
            raise ValidationError("GPU startup completion retains an unavailable native facility.")
    expected = {(row.record.operation_id, row.goal): row.record for row in scope.recorded}
    if scope.legacy_plan is not None:
        for plan in scope.legacy_plan.devices:
            if plan.rejection is not None:
                raise ValidationError("GPU startup legacy scope contains a rejected peer.")
            if plan.record is not None:
                expected[(plan.record.operation_id, GPUStartupRecordedGoal.UNCOMMITTED_LEGACY)] = (
                    plan.record
                )
    rows = verification.recorded_readbacks + verification.legacy_readbacks
    if len(rows) != len(expected) or len(
        {(row.record.operation_id, row.goal) for row in rows}
    ) != len(rows):
        raise ValidationError("GPU startup completion omits or duplicates an actual goal.")
    for row in rows:
        original = expected.get((row.record.operation_id, row.goal))
        if original is None or recovery_scope_digest(original) != recovery_scope_digest(row.record):
            raise ValidationError("GPU startup completion changed an immutable native goal.")
        selected = require_current_recovery_record(
            replace(read, revision=row.prepared.store_revision), row.prepared
        )
        if selected != row.record:
            raise ValidationError("GPU startup final read changed its actual native checkpoint.")
        require_complete_recovery_checkpoint(selected, row.result)
        reduction = reduce_gpu_control_result(row.result, prepared=row.prepared)
        if row.goal == GPUStartupRecordedGoal.ORIGINAL:
            require_original_recovery_readback(selected, row.result)
        elif not reduction.persistence_eligible:
            raise ValidationError("GPU startup legacy completion lacks actual target proof.")
    expected_devices = {row.record.device_id for row in rows}
    if {record.device_id for record in read.recovery_records} != expected_devices:
        raise ValidationError("GPU startup final read omits or adds retained recovery scope.")
    for record in read.recovery_records:
        if isinstance(record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord):
            if (
                record.legacy_commit is None
                or control_state_digest(read.payload, record.device_id)
                != record.legacy_commit.completed_control_state_digest
            ):
                raise ValidationError("GPU startup legacy saved completion is unavailable.")


def _require_saved_projections(
    initial: GPUSlotReadResult, final: GPUSlotReadResult, policy: GPUStartupScopePolicy
) -> None:
    initial_devices = require_json_dict(initial.payload.get("devices"), label="GPU initial devices")
    final_devices = require_json_dict(final.payload.get("devices"), label="GPU final devices")
    committed = {
        record.device_id
        for record in final.recovery_records
        if isinstance(record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord)
    }
    for device_id in set(initial_devices) | set(final_devices):
        if device_id in committed:
            continue
        comparable = copy.deepcopy(final.payload)
        entries = require_json_dict(comparable.get("devices"), label="GPU final devices")
        original_entry, final_entry = initial_devices.get(device_id), entries.get(device_id)
        if (
            policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL
            and isinstance(original_entry, dict)
            and isinstance(final_entry, dict)
        ):
            original_boot, final_boot = original_entry.get("boot"), final_entry.get("boot")
            if isinstance(original_boot, dict) and isinstance(final_boot, dict):
                if final_boot.get("enabled") is False and "enabled" in original_boot:
                    final_boot["enabled"] = original_boot["enabled"]
        if control_state_digest(initial.payload, device_id) != control_state_digest(
            comparable, device_id
        ):
            raise ValidationError("GPU startup original saved authority changed.")


def _completed_payload(read: GPUSlotReadResult) -> JSONDict:
    payload = copy.deepcopy(read.payload)
    payload["recovery"] = {}
    return payload


def _discard_registered(
    pending: dict[str, GPURecoveryPendingCommit], authority: GPUStartupPendingAuthority
) -> None:
    for device_id, candidate in tuple(pending.items()):
        if candidate.startup_authority is authority:
            del pending[device_id]

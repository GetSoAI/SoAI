"""SoAI - Frozen single-device native preparation and durable application [backend/hardware/gpu_tuning/direct_prepared_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import (
    GPUControlCommitIntent,
    GPUControlPreflightRejection,
)
from core.hardware.gpu_control_types import (
    GPURecoveryAdmissionState,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.hardware.gpu_operation_results import build_gpu_result
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.types.json import JSONDict
from core.types.json_value import require_json_dict
from hardware.gpu_tuning.control_backend_selection import group_settings_by_control_backend
from hardware.gpu_tuning.control_operation_finalization import GPUControlFinalizationTarget
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.control_saved_state_authority import (
    apply_verified_user_state,
    control_state_digest,
    require_saved_control_authority,
)
from hardware.gpu_tuning.control_worker_results import (
    GPU_CONTROL_WORKER_EXCEPTIONS,
    GPUControlOperationOutcome,
)
from hardware.gpu_tuning.effective_control_state import build_apply_settings_for_modes
from hardware.gpu_tuning.mutation_policy import hardware_mutation_disabled_payload
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.runtime_original_restoration import (
    reconciled_recovery_outcome,
    restore_recorded_originals,
)
from hardware.gpu_tuning.vendor_backend_apply import (
    apply_vendor_backend_settings,
    prepare_vendor_backend_settings,
)
from hardware.vendors.nvidia.nvml_clock_preparation import selected_nvml_clock_facilities

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_control_types import GPUControlCommitAcknowledgement
    from core.hardware.gpu_recovery_records import GPURecoveryRecord
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies


__all__ = (
    "GPUPreparedSettingsPlan",
    "prepare_gpu_settings_plan",
    "execute_gpu_settings_plan",
    "sync_apply_prepared_gpu_settings",
    "rejected_gpu_settings_outcome",
)


@dataclass(frozen=True, slots=True)
class GPUPreparedSettingsPlan:
    target: GPUPhysicalDevice
    record: GPURecoveryRecord
    result_key: str
    scope_digest: str

    @property
    def finalization_target(self) -> GPUControlFinalizationTarget:
        intent = self.record.commit_intent
        if intent is None:
            raise ValidationError("GPU native plan lacks its actual commit intent.")
        return GPUControlFinalizationTarget(self.target, intent, self.result_key, self.scope_digest)


def prepare_gpu_settings_plan(
    deps: GpuSettingsApplyDependencies,
    *,
    operation_id: str,
    target: GPUPhysicalDevice,
    gpu_index: int,
    capabilities: JSONDict,
    settings: JSONDict,
    field_modes: JSONDict,
    commit_intent: GPUControlCommitIntent,
    cancellation_token: CancellationTokenProtocol,
) -> GPUPreparedSettingsPlan | GPUControlPreflightRejection:
    cancellation_token.raise_if_cancelled()
    apply_settings = build_apply_settings_for_modes(settings, field_modes)
    grouped = group_settings_by_control_backend(apply_settings, capabilities)
    normalized = {field: value for bucket in grouped.values() for field, value in bucket.items()}
    modes = {field: field_modes[field] for field in normalized}
    if set(commit_intent.user_fields) != set(normalized):
        raise ValidationError("GPU user intent must cover exactly its selected native user fields.")
    record = prepare_vendor_backend_settings(
        executor=deps.executor,
        logger=deps.logger,
        nvidia_settings_controller=deps.nvidia_settings_controller,
        gpu_services=deps.gpu_services,
        target=target,
        operation_id=operation_id,
        normalized_settings=normalized,
        requested_modes=modes,
        grouped_settings=grouped,
        clock_control_types=selected_nvml_clock_facilities(capabilities, normalized),
    )
    cancellation_token.raise_if_cancelled()
    if isinstance(record, GPUControlPreflightRejection):
        return record
    record = replace(copy.deepcopy(record), commit_intent=commit_intent)
    if record.pci_bdf_observations is None:
        raise ValidationError("GPU native plan discarded actual PCI observations.")
    frozen_target = replace(
        target, identity=record.physical_identity, pci_bdf_observations=record.pci_bdf_observations
    )
    return GPUPreparedSettingsPlan(
        frozen_target, record, str(gpu_index), recovery_scope_digest(record)
    )


def execute_gpu_settings_plan(
    deps: GpuSettingsApplyDependencies,
    plan: GPUPreparedSettingsPlan,
    cancellation_token: CancellationTokenProtocol,
) -> GPUControlOperationOutcome:
    plan = copy.deepcopy(plan)
    if recovery_scope_digest(plan.record) != plan.scope_digest:
        raise ValidationError("GPU planned request changed after complete native preparation.")
    cancellation_token.raise_if_cancelled()
    if deps.runtime_flags.hardware_mutation_disabled:
        disabled_payload = hardware_mutation_disabled_payload()
        disabled_payload["gpus"] = {
            plan.result_key: build_gpu_result(
                errors=["Hardware mutation is disabled."], changed=False
            )
        }
        return GPUControlOperationOutcome(
            disabled_payload, (), False, False, None, False, (), (), (), None, None
        )
    recovery = deps.native_control_recovery
    admission = recovery.inspect(plan.target)
    if (
        admission.state == GPURecoveryAdmissionState.RECOVERY_REQUIRED
        and admission.operation_id is not None
    ):
        return reconciled_recovery_outcome(
            plan.result_key, restore_recorded_originals(deps, plan.target, cancellation_token)
        )
    try:
        prepared = recovery.prepare(plan.target, plan.record)
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        rejected = rejected_gpu_settings_outcome(
            plan.result_key,
            GPUControlPreflightRejection("gpu_control_preparation_failed", str(exception)),
        )
        return replace(rejected, failure=exception)
    result, prepared = apply_vendor_backend_settings(
        executor=deps.executor,
        logger=deps.logger,
        nvidia_settings_controller=deps.nvidia_settings_controller,
        gpu_services=deps.gpu_services,
        target=plan.target,
        record=plan.record,
        prepared=prepared,
        recovery=recovery,
        cancellation_token=cancellation_token,
    )
    reduction = reduce_gpu_control_result(result, prepared=prepared)
    restoration = (
        restore_recorded_originals(deps, plan.target, cancellation_token)
        if reduction.unresolved
        and reduction.changed is not False
        and not cancellation_token.thread_event.is_set()
        else None
    )
    committed: tuple[GPUControlCommitAcknowledgement, ...] = ()
    committed_snapshots: JSONDict = {}
    metadata_changed = False
    failure: Exception | None = None
    uncertain = False
    if not reduction.unresolved:
        try:
            with deps.storage.lock:
                saved = copy.deepcopy(deps.storage.read_payload().payload)
                if reduction.persistence_eligible:
                    require_saved_control_authority(saved, plan.record)
                acknowledgement = recovery.finish(prepared, result)
            if acknowledgement is not None:
                committed = (acknowledgement,)
                apply_verified_user_state(saved, plan.record, acknowledgement.committed_at)
                devices = require_json_dict(saved["devices"], label="GPU committed device states")
                committed_snapshots[plan.target.device_id] = copy.deepcopy(
                    devices[plan.target.device_id]
                )
                metadata_changed = (
                    control_state_digest(saved, plan.target.device_id)
                    != acknowledgement.commit_intent.expected_control_state_digest
                )
        except GPUSlotWriteError as slot_exception:
            failure = slot_exception
            uncertain = slot_exception.reason == GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN
        except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
            failure = exception
    cancelled = result.failure_codes == ("operation_cancelled",)
    successful = reduction.persistence_eligible and bool(committed) and failure is None
    entry = build_gpu_result(
        messages=["GPU settings verified and saved."] if successful else [],
        errors=(
            []
            if successful or cancelled
            else ["GPU settings could not be verified and saved safely."]
        ),
        changed=reduction.changed,
    )
    payload: JSONDict = {"success": successful, "gpus": {plan.result_key: entry}}
    if reduction.changed is not None:
        payload["changed"] = True if metadata_changed else reduction.changed
    if committed:
        payload["applied_at"] = committed[0].committed_at
        payload["committed_state_snapshots"] = committed_snapshots
    if restoration is None:
        return GPUControlOperationOutcome(
            payload,
            (reduction,),
            metadata_changed,
            uncertain,
            failure,
            cancelled,
            (result,),
            (),
            committed,
            prepared.dirty_marker_receipt,
            None,
        )
    payload["original_restoration"] = restoration.state.value
    return GPUControlOperationOutcome(
        payload,
        (reduction, *restoration.reductions),
        metadata_changed,
        uncertain or restoration.persistence_uncertain,
        failure,
        cancelled,
        (result,) if restoration.result is None else (result, restoration.result),
        (),
        committed,
        (
            prepared.dirty_marker_receipt
            if restoration.prepared is None
            else restoration.prepared.dirty_marker_receipt
        ),
        None,
    )


def sync_apply_prepared_gpu_settings(
    deps: GpuSettingsApplyDependencies,
    *,
    operation_id: str,
    target: GPUPhysicalDevice,
    gpu_index: int,
    capabilities: JSONDict,
    settings: JSONDict,
    field_modes: JSONDict,
    commit_intent: GPUControlCommitIntent,
    cancellation_token: CancellationTokenProtocol,
) -> GPUControlOperationOutcome:
    plan = prepare_gpu_settings_plan(
        deps,
        operation_id=operation_id,
        target=target,
        gpu_index=gpu_index,
        capabilities=capabilities,
        settings=settings,
        field_modes=field_modes,
        commit_intent=commit_intent,
        cancellation_token=cancellation_token,
    )
    if isinstance(plan, GPUControlPreflightRejection):
        return rejected_gpu_settings_outcome(str(gpu_index), plan)
    return execute_gpu_settings_plan(deps, plan, cancellation_token)


def rejected_gpu_settings_outcome(
    result_key: str, rejection: GPUControlPreflightRejection
) -> GPUControlOperationOutcome:
    payload: JSONDict = {
        "success": False,
        "code": rejection.code,
        "changed": False,
        "gpus": {
            result_key: build_gpu_result(
                errors=["GPU settings preparation could not complete safely."], changed=False
            )
        },
    }
    return GPUControlOperationOutcome(
        payload, (), False, False, None, False, (), (rejection,), (), None, None
    )

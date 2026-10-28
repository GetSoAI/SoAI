"""SoAI - GPU startup dirty recovery reset selection [backend/hardware/gpu_tuning/startup_recovery_resets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import replace
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import (
    GPUControlReduction,
    GPUControlStartupDisposition,
    GPUControlStartupResult,
    GPURecoveryAdmission,
    GPURecoveryAdmissionState,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.hardware.gpu_operation_results import build_gpu_result
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from hardware.gpu_tuning.control_operation_finalization import finalize_gpu_control_effects
from hardware.gpu_tuning.control_recovery_checkpoints import create_prepared_control_receipt
from hardware.gpu_tuning.control_recovery_completion import require_original_recovery_readback
from hardware.gpu_tuning.control_recovery_records import require_current_recovery_record
from hardware.gpu_tuning.control_worker_results import (
    GPU_CONTROL_WORKER_EXCEPTIONS,
    GPUControlOperationOutcome,
)
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.startup import prepare_startup_legacy_slots, require_fresh_startup_scope
from hardware.gpu_tuning.startup_apply_flow import (
    GPUStartupNativeStep,
    apply_startup_planned_legacy,
    apply_startup_recorded_goal,
)
from hardware.gpu_tuning.startup_native_verification import verify_gpu_control_startup_scope
from hardware.gpu_tuning.startup_reconciliation_authority import reconcile_startup_legacy_state
from hardware.gpu_tuning.startup_recovery_completion import commit_startup_boot_disablement
from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedGoal, GPUStartupScopePolicy

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_control_types import GPUControlCommitAcknowledgement, GPUSlotReadResult
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies
    from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope


__all__ = ("execute_startup_recovery",)


def execute_startup_recovery(
    deps: GpuSettingsApplyDependencies,
    cancellation_token: CancellationTokenProtocol,
    *,
    scope: GPUControlStartupScope,
    initial_read: GPUSlotReadResult,
    operation_id: str,
) -> GPUControlOperationOutcome:
    scope, initial_read = copy.deepcopy((scope, initial_read))
    cancellation_token.raise_if_cancelled()
    if deps.runtime_flags.hardware_mutation_disabled:
        return GPUControlOperationOutcome(
            {},
            (),
            False,
            False,
            None,
            False,
            (),
            (),
            (),
            None,
            GPUControlStartupResult(GPUControlStartupDisposition.SKIPPED_POLICY_DISABLED, None),
        )
    pending = deps.native_control_recovery.startup_scope.pending
    if pending and any(candidate.startup_authority is not None for candidate in pending.values()):
        candidate = next(iter(pending.values()))
        authority = candidate.startup_authority
        if authority is None:
            raise ValidationError("GPU aggregate repair changed its complete pending union.")
        deps.native_control_recovery.startup_scope.repair(authority.verification)
        return GPUControlOperationOutcome(
            {},
            (),
            False,
            False,
            None,
            False,
            (),
            (),
            (),
            None,
            _observed(deps.native_control_recovery.startup_admission()),
        )
    require_fresh_startup_scope(deps, scope, initial_read, operation_id)
    repaired: dict[str, GPUControlCommitAcknowledgement] = {}
    for candidate in tuple(pending.values()):
        repaired_acknowledgement = reconcile_startup_legacy_state(
            deps.storage,
            pending=pending,
            prepared=candidate.prepared,
            dirty_flag_path=deps.native_control_recovery.dependencies.dirty_flag_path,
        )
        repaired[candidate.prepared.operation_id] = repaired_acknowledgement
    cancellation_token.raise_if_cancelled()
    owner = deps.native_control_recovery.startup_scope
    owner.bind(scope)
    try:
        steps: list[GPUStartupNativeStep] = []
        failure = None
        cancelled = False
        extra_reductions: tuple[GPUControlReduction, ...] = ()
        try:
            planned = prepare_startup_legacy_slots(deps, scope, operation_id, cancellation_token)
            for row in scope.recorded:
                if row.state == GPUPhysicalBindingState.BOUND:
                    step = apply_startup_recorded_goal(deps, row, cancellation_token)
                    acknowledgement = repaired.get(row.record.operation_id)
                    if acknowledgement is not None:
                        step = replace(step, acknowledgement=acknowledgement)
                    steps.append(step)
            if scope.legacy_plan is not None:
                for plan in scope.legacy_plan.devices:
                    if plan.record is not None and plan.rejection is None:
                        cancellation_token.raise_if_cancelled()
                        with deps.storage.lock:
                            read = deps.storage.read_payload()
                            previous = planned[plan.record.operation_id]
                            selected = require_current_recovery_record(
                                replace(read, revision=previous.store_revision), previous
                            )
                            prepared = create_prepared_control_receipt(
                                plan.target, selected, read, owner.live_receipt
                            )
                        steps.append(
                            apply_startup_planned_legacy(
                                deps, plan.target, prepared, cancellation_token
                            )
                        )
        except TaskCancelledError:
            cancelled = True
        except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
            failure = exception
            extra_reductions = (GPUControlReduction(None, True, False, False),)
        outcome = _startup_outcome(deps, scope, steps, failure, cancelled, extra_reductions)
        try:
            outcome = finalize_gpu_control_effects(deps.delivery_dependencies.effects, outcome)
            if (
                outcome.failure is None
                and not outcome.cancelled
                and all(_step_resolved(step) for step in steps)
            ):
                cancellation_token.raise_if_cancelled()
                recorded = tuple(
                    step.readback
                    for step in steps
                    if any(
                        row.record.operation_id == step.readback.record.operation_id
                        for row in scope.recorded
                    )
                )
                legacy = tuple(step.readback for step in steps if step.readback not in recorded)
                verification = verify_gpu_control_startup_scope(
                    scope,
                    executor=deps.executor,
                    logger=deps.logger,
                    gpu_services=deps.gpu_services,
                    acquisition_id=f"{operation_id}:final",
                    recorded_readbacks=recorded,
                    legacy_readbacks=legacy,
                )
                if scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
                    _read, affected = commit_startup_boot_disablement(
                        deps.storage, initial_read=initial_read, verification=verification
                    )
                    if affected:
                        outcome = replace(
                            outcome,
                            metadata_changed=True,
                            payload={**outcome.payload, "startup_boot_snapshots": affected},
                        )
                owner.finish(initial_read, verification)
                outcome = replace(
                    outcome,
                    startup_result=_observed(deps.native_control_recovery.startup_admission()),
                )
        except TaskCancelledError:
            outcome = replace(outcome, cancelled=True)
        except GPUSlotWriteError as slot_exception:
            outcome = replace(
                outcome,
                failure=slot_exception,
                persistence_uncertain=outcome.persistence_uncertain
                or slot_exception.reason == GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN,
            )
        except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
            outcome = replace(outcome, failure=exception)
        return outcome

    finally:
        owner.release(scope)


def _observed(admission: GPURecoveryAdmission) -> GPUControlStartupResult:
    return GPUControlStartupResult(GPUControlStartupDisposition.ADMISSION_OBSERVED, admission)


def _startup_outcome(
    deps: GpuSettingsApplyDependencies,
    scope: GPUControlStartupScope,
    steps: list[GPUStartupNativeStep],
    failure: Exception | None,
    cancelled: bool,
    extra_reductions: tuple[GPUControlReduction, ...],
) -> GPUControlOperationOutcome:
    results = tuple(step.readback.result for step in steps)
    reductions = (
        tuple(
            reduce_gpu_control_result(step.readback.result, prepared=step.readback.prepared)
            for step in steps
        )
        + extra_reductions
    )
    acknowledgements = tuple(
        step.acknowledgement for step in steps if step.acknowledgement is not None
    )
    failures = [step.failure for step in steps if step.failure is not None]
    if failure is not None:
        failures.append(failure)
    combined = (
        failures[0]
        if len(failures) == 1
        else (ExceptionGroup("GPU startup failed.", failures) if failures else None)
    )
    admission = deps.native_control_recovery.startup_admission()
    if any(row.state == GPUPhysicalBindingState.IDENTITY_CONFLICT for row in scope.recorded):
        admission = GPURecoveryAdmission(GPURecoveryAdmissionState.IDENTITY_CONFLICT, None)
    device_ids = [device.device_id for device in scope.physical_snapshot.devices]
    device_ids.extend(row.record.device_id for row in scope.recorded)
    if scope.legacy_plan is not None:
        device_ids.extend(row.target.device_id for row in scope.legacy_plan.devices)
    payload = {
        device_id: build_gpu_result(
            messages=["GPU startup target has not been verified."], changed=False
        )
        for device_id in dict.fromkeys(device_ids)
    }
    for step in steps:
        reduced = reduce_gpu_control_result(step.readback.result, prepared=step.readback.prepared)
        payload[step.readback.result.target.device_id] = build_gpu_result(
            messages=["GPU startup native state verified."] if _step_resolved(step) else [],
            errors=[] if _step_resolved(step) else ["GPU startup requires recovery."],
            changed=reduced.changed,
        )
    return GPUControlOperationOutcome(
        {"gpus": payload},
        reductions,
        bool(acknowledgements),
        any(step.persistence_uncertain for step in steps),
        combined,
        cancelled or any("operation_cancelled" in result.failure_codes for result in results),
        results,
        (),
        acknowledgements,
        deps.native_control_recovery.startup_scope.live_receipt,
        _observed(admission),
    )


def _step_resolved(step: GPUStartupNativeStep) -> bool:
    if step.failure is not None or step.readback.result.failure_codes:
        return False
    if step.readback.goal != GPUStartupRecordedGoal.ORIGINAL:
        return reduce_gpu_control_result(
            step.readback.result, prepared=step.readback.prepared
        ).persistence_eligible
    try:
        require_original_recovery_readback(step.readback.record, step.readback.result)
    except ValidationError:
        return False
    return True

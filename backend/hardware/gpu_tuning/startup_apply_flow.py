"""SoAI - GPU tuning startup application flow helpers [backend/hardware/gpu_tuning/startup_apply_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import GPUSlotWriteError, GPUSlotWriteFailure
from core.hardware.gpu_recovery_records import (
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from hardware.gpu_tuning.control_recovery_records import require_current_recovery_record
from hardware.gpu_tuning.control_worker_results import GPU_CONTROL_WORKER_EXCEPTIONS
from hardware.gpu_tuning.native_backend_observations import read_startup_record_goal
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.startup_reconciliation_authority import commit_startup_legacy_state
from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedGoal, GPUStartupScopeReadback
from hardware.gpu_tuning.vendor_backend_apply import (
    apply_vendor_backend_settings,
    restore_vendor_backend_originals,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_control_types import (
        GPUControlCommitAcknowledgement,
        GPUControlResult,
        GPUPreparedControl,
    )
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.gpu_recovery_records import GPURecoveryRecord
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies
    from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedScope


__all__ = (
    "GPUStartupNativeStep",
    "apply_startup_recorded_goal",
    "apply_startup_planned_legacy",
    "complete_startup_native_step",
)


@dataclass(frozen=True, slots=True)
class GPUStartupNativeStep:
    readback: GPUStartupScopeReadback
    acknowledgement: GPUControlCommitAcknowledgement | None
    failure: Exception | None
    persistence_uncertain: bool


def apply_startup_recorded_goal(
    deps: GpuSettingsApplyDependencies,
    row: GPUStartupRecordedScope,
    cancellation_token: CancellationTokenProtocol,
) -> GPUStartupNativeStep:
    cancellation_token.raise_if_cancelled()
    target = row.target
    if target is None:
        raise ValidationError("GPU startup native goal lacks its bound physical target.")
    recovery = deps.native_control_recovery
    prepared = recovery.resume_startup_recorded(
        target, operation_id=row.record.operation_id, goal=row.goal
    )
    with deps.storage.lock:
        record = require_current_recovery_record(deps.storage.read_payload(), prepared)
    if row.goal == GPUStartupRecordedGoal.ORIGINAL:
        result, prepared = restore_vendor_backend_originals(
            executor=deps.executor,
            logger=deps.logger,
            nvidia_settings_controller=deps.nvidia_settings_controller,
            gpu_services=deps.gpu_services,
            target=target,
            record=record,
            prepared=prepared,
            recovery=recovery,
            cancellation_token=cancellation_token,
        )
    else:
        result = read_startup_record_goal(
            record,
            prepared,
            row.goal,
            executor=deps.executor,
            logger=deps.logger,
            gpu_services=deps.gpu_services,
        )
        prepared = recovery.record_result(prepared, result)
    return complete_startup_native_step(deps, target, prepared, record, result, row.goal)


def apply_startup_planned_legacy(
    deps: GpuSettingsApplyDependencies,
    target: GPUPhysicalDevice,
    prepared: GPUPreparedControl,
    cancellation_token: CancellationTokenProtocol,
) -> GPUStartupNativeStep:
    cancellation_token.raise_if_cancelled()
    with deps.storage.lock:
        record = require_current_recovery_record(deps.storage.read_payload(), prepared)
    result, prepared = apply_vendor_backend_settings(
        executor=deps.executor,
        logger=deps.logger,
        nvidia_settings_controller=deps.nvidia_settings_controller,
        gpu_services=deps.gpu_services,
        target=target,
        record=record,
        prepared=prepared,
        recovery=deps.native_control_recovery,
        cancellation_token=cancellation_token,
    )
    return complete_startup_native_step(
        deps, target, prepared, record, result, GPUStartupRecordedGoal.UNCOMMITTED_LEGACY
    )


def complete_startup_native_step(
    deps: GpuSettingsApplyDependencies,
    target: GPUPhysicalDevice,
    prepared: GPUPreparedControl,
    record: GPURecoveryRecord,
    result: GPUControlResult,
    goal: GPUStartupRecordedGoal,
) -> GPUStartupNativeStep:
    acknowledgement = None
    failure: Exception | None = None
    uncertain = False
    reduction = reduce_gpu_control_result(result, prepared=prepared)
    selected = replace(
        copy.deepcopy(record), members=tuple(member.recovery_member for member in result.members)
    )
    try:
        with deps.storage.lock:
            read = deps.storage.read_payload()
            selected = copy.deepcopy(require_current_recovery_record(read, prepared))
            retained = next(
                item for item in read.recovery_records if item.device_id == target.device_id
            )
            if goal != GPUStartupRecordedGoal.ORIGINAL and reduction.persistence_eligible:
                if not isinstance(
                    retained, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord
                ):
                    raise ValidationError(
                        "GPU startup target completion lacks its retained tagged slot."
                    )
                acknowledgement = commit_startup_legacy_state(
                    deps.storage,
                    pending=deps.native_control_recovery.startup_scope.pending,
                    record=retained,
                    prepared=prepared,
                    result=result,
                )
    except GPUSlotWriteError as exception:
        failure = exception
        uncertain = exception.reason == GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        failure = exception
    return GPUStartupNativeStep(
        GPUStartupScopeReadback(selected, goal, result, prepared),
        acknowledgement,
        failure,
        uncertain,
    )

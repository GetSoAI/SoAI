"""SoAI - GPU tuning boot preference application at startup [backend/hardware/gpu_tuning/startup_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from core.concurrency.cancellation import CancellationToken
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import GPUControlCommitIntent
from core.hardware.gpu_control_types import (
    GPUControlStartupDisposition,
    GPUControlStartupResult,
    GPUSlotReadError,
)
from core.hardware.gpu_recovery_failures import GPURecoveryTargetConflictError
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS
from core.types.json_value import require_json_dict
from hardware.gpu_tuning.control_operation_delivery import run_finalized_gpu_control_operation
from hardware.gpu_tuning.control_saved_state_authority import control_state_digest
from hardware.gpu_tuning.control_worker_results import GPUControlOperationOutcome
from hardware.gpu_tuning.dirty_shutdown_flag import require_gpu_marker_store_read
from hardware.gpu_tuning.gpu_settings_sync_apply import sync_set_gpu_settings
from hardware.gpu_tuning.mutation_leases import GPUControlMetadataScope
from hardware.gpu_tuning.mutation_policy import hardware_mutation_disabled_payload
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.service_dependencies import GPUStartupAcquisitionResources
from hardware.gpu_tuning.startup import GPUStartupBootPreparation, prepare_startup_boot_slots
from hardware.gpu_tuning.startup_recovery_resets import execute_startup_recovery
from hardware.gpu_tuning.startup_scope_accounting import (
    require_empty_startup_accounting,
    startup_cleanup_targets,
)
from hardware.gpu_tuning.startup_scope_acquisition import build_gpu_control_startup_scope
from hardware.gpu_tuning.startup_scope_types import GPUStartupScopePolicy

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.events.protocols import EventBusProtocol
    from core.hardware.gpu_control_types import GPUSlotReadResult
    from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies
    from hardware.gpu_tuning.startup_scope_types import (
        GPUControlStartupScope,
        GPULegacyResetDevicePlan,
    )


__all__ = (
    "prepare_startup_recovery_scope",
    "apply_startup_gpu_settings",
    "apply_clean_startup_boot",
    "commit_startup_boot_metadata",
)

OPERATION_GPU_STARTUP_PHYSICAL_TARGET = "hardware.gpu_tuning.startup.physical_target"


def prepare_startup_recovery_scope(
    deps: GpuSettingsApplyDependencies,
    *,
    operation_id: str,
) -> tuple[GPUSlotReadResult, GPUControlStartupScope]:
    recovery = deps.native_control_recovery
    with deps.storage.lock:
        pending = recovery.startup_scope.pending
        if pending and any(
            candidate.startup_authority is not None for candidate in pending.values()
        ):
            authority = next(iter(pending.values())).startup_authority
            if authority is None:
                raise ValidationError("GPU aggregate repair changed its retained authority.")
            return copy.deepcopy((authority.final_read, authority.verification.scope))
        initial = copy.deepcopy(deps.storage.read_payload())
        policy = recovery.startup_scope.policy
        require_gpu_marker_store_read(
            initial,
            marker_path=recovery.dependencies.dirty_flag_path,
            pending_devices=tuple(recovery.startup_scope.pending),
        )
    scope = build_gpu_control_startup_scope(
        executor=deps.executor,
        logger=deps.logger,
        gpu_services=deps.gpu_services,
        runtime_platform=deps.gpu_services.nvidia_nvml_gate.runtime_platform,
        intel_executable=deps.gpu_services.intel_executable,
        acquisition_id=operation_id,
        policy=policy,
        initial_records=initial.recovery_records,
    )
    if scope.legacy_plan is not None:
        plans: list[GPULegacyResetDevicePlan] = []
        for plan in scope.legacy_plan.devices:
            record = plan.record
            if record is not None:
                user_fields = tuple(
                    field
                    for field in record.requested_settings
                    if field in GPU_DIRECT_SETTING_FIELDS
                )
                intent = GPUControlCommitIntent(
                    user_fields,
                    control_state_digest(initial.payload, record.device_id),
                    None,
                    None,
                    False,
                )
                record = replace(record, commit_intent=intent)
            plans.append(replace(plan, record=record))
        scope = replace(scope, legacy_plan=replace(scope.legacy_plan, devices=tuple(plans)))
    return copy.deepcopy((initial, scope))


async def apply_startup_gpu_settings(
    *,
    settings_deps: GpuSettingsApplyDependencies,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    dirty_flag_path: str,
) -> GPUControlStartupResult:
    deps = settings_deps
    delivery = deps.delivery_dependencies
    if (
        delivery.event_bus is not event_bus
        or delivery.main_loop is not main_loop
        or delivery.cancellation_binder is not cancellation_binder
        or delivery.finalizer_tracker is not finalizer_tracker
        or dirty_flag_path != deps.native_control_recovery.dependencies.dirty_flag_path
    ):
        raise ValidationError("GPU startup requires its actual service resource owners.")
    if deps.runtime_flags.hardware_mutation_disabled:
        return GPUControlStartupResult(GPUControlStartupDisposition.SKIPPED_POLICY_DISABLED, None)
    operation_id = f"gpu-startup:{uuid4()}"
    recovery = deps.native_control_recovery
    try:
        with deps.storage.lock:
            read = deps.storage.read_payload()
            policy = recovery.startup_scope.policy
            require_gpu_marker_store_read(
                read,
                marker_path=dirty_flag_path,
                pending_devices=tuple(recovery.startup_scope.pending),
            )
        if (
            policy == GPUStartupScopePolicy.RECORDED_RECOVERY
            and not read.recovery_records
            and not recovery.startup_scope.pending
        ):
            return await apply_clean_startup_boot(deps, operation_id=operation_id)
    except GPUSlotReadError:
        return GPUControlStartupResult(
            GPUControlStartupDisposition.ADMISSION_OBSERVED, recovery.startup_admission()
        )
    try:
        initial, scope = await run_joined_thread_call(
            partial(prepare_startup_recovery_scope, deps, operation_id=operation_id),
            task_name=f"{operation_id}:preparation",
            retain_resources_until_complete=True,
        )
    except GPUSlotReadError:
        return GPUControlStartupResult(
            GPUControlStartupDisposition.ADMISSION_OBSERVED,
            deps.native_control_recovery.startup_admission(),
        )
    try:
        cleanup_targets = startup_cleanup_targets(scope)
    except GPURecoveryTargetConflictError as exception:
        log_handled_exception(
            deps.logger,
            exception,
            message="GPU recovery target is unavailable; mutations remain restricted.",
            operation=OPERATION_GPU_STARTUP_PHYSICAL_TARGET,
            level="warning",
        )
        return GPUControlStartupResult(
            GPUControlStartupDisposition.ADMISSION_OBSERVED, recovery.startup_admission()
        )
    if not cleanup_targets:
        try:
            require_empty_startup_accounting(scope)
        except ValidationError:
            return GPUControlStartupResult(
                GPUControlStartupDisposition.ADMISSION_OBSERVED,
                deps.native_control_recovery.startup_admission(),
            )
    return await run_finalized_gpu_control_operation(
        deps.control_operation_state,
        delivery,
        operation_id=operation_id,
        targets=scope,
        startup_resources=GPUStartupAcquisitionResources(
            deps.executor, deps.logger, deps.gpu_services
        ),
        worker=partial(
            execute_startup_recovery,
            deps,
            scope=scope,
            initial_read=initial,
            operation_id=operation_id,
        ),
    )


async def apply_clean_startup_boot(
    deps: GpuSettingsApplyDependencies,
    *,
    operation_id: str,
) -> GPUControlStartupResult:
    token = CancellationToken(operation_id, owner="gpu-startup-preparation")

    def cancel_preparation() -> None:
        token.cancel("GPU startup client cancelled preparation.")

    preparation = await run_joined_thread_call(
        partial(prepare_startup_boot_slots, deps, token, operation_id=operation_id),
        task_name=f"{operation_id}:boot-preparation",
        retain_resources_until_complete=True,
        on_cancel=cancel_preparation,
    )
    if isinstance(preparation, GPUControlOperationOutcome):
        deps.logger.warning("GPU boot preferences could not be prepared safely.")
    else:
        if preparation.changed_devices:
            metadata = await run_finalized_gpu_control_operation(
                deps.control_operation_state,
                deps.delivery_dependencies,
                operation_id=f"{operation_id}:metadata",
                targets=GPUControlMetadataScope(preparation.changed_devices),
                startup_resources=None,
                worker=partial(commit_startup_boot_metadata, deps, preparation),
            )
            if metadata.get("code") == "hardware_mutation_disabled":
                return GPUControlStartupResult(
                    GPUControlStartupDisposition.SKIPPED_POLICY_DISABLED, None
                )
            if not is_success_result(
                metadata, logger=deps.logger, operation="hardware.gpu_tuning.startup.metadata"
            ):
                return GPUControlStartupResult(
                    GPUControlStartupDisposition.ADMISSION_OBSERVED,
                    deps.native_control_recovery.startup_admission(),
                )
        if preparation.plans:
            result = await run_finalized_gpu_control_operation(
                deps.control_operation_state,
                deps.delivery_dependencies,
                operation_id=operation_id,
                targets=tuple(plan.finalization_target for plan in preparation.plans),
                startup_resources=None,
                worker=partial(sync_set_gpu_settings, deps, preparation.plans),
            )
            if result.get("code") == "hardware_mutation_disabled":
                return GPUControlStartupResult(
                    GPUControlStartupDisposition.SKIPPED_POLICY_DISABLED, None
                )
            if not is_success_result(
                result, logger=deps.logger, operation="hardware.gpu_tuning.startup.boot"
            ):
                deps.logger.warning("GPU boot preference application requires attention.")
    return GPUControlStartupResult(
        GPUControlStartupDisposition.ADMISSION_OBSERVED,
        deps.native_control_recovery.startup_admission(),
    )


def commit_startup_boot_metadata(
    deps: GpuSettingsApplyDependencies,
    preparation: GPUStartupBootPreparation,
    cancellation_token: CancellationTokenProtocol,
) -> GPUControlOperationOutcome:
    preparation = copy.deepcopy(preparation)
    cancellation_token.raise_if_cancelled()
    if deps.runtime_flags.hardware_mutation_disabled:
        payload = hardware_mutation_disabled_payload()
        return GPUControlOperationOutcome(
            payload, (), False, False, None, False, (), (), (), None, None
        )
    with deps.storage.lock:
        current = deps.storage.read_payload()
        if current != preparation.initial_read or current.recovery_records:
            raise ValidationError("GPU startup metadata authority changed before commit.")
        deps.storage.write_payload(preparation.candidate_payload, expected_read=current)
        final = deps.storage.read_payload()
        if final.payload != preparation.candidate_payload:
            raise ValidationError("GPU startup metadata completion changed its exact candidate.")
    devices = require_json_dict(final.payload["devices"], label="GPU startup metadata devices")
    snapshots = {
        device_id: copy.deepcopy(devices[device_id]) for device_id in preparation.changed_devices
    }
    return GPUControlOperationOutcome(
        {"success": True, "startup_metadata_snapshots": snapshots},
        (),
        True,
        False,
        None,
        False,
        (),
        (),
        (),
        None,
        None,
    )

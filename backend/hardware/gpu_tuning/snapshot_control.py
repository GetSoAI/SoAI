"""SoAI - Snapshot-owned MCP GPU control preparation and completion [backend/hardware/gpu_tuning/snapshot_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from core.errors.exceptions import GPUControlInputValidationError, ValidationError
from core.hardware.gpu_control_operation_types import (
    GPUControlCommitIntent,
    GPUControlPreflightRejection,
)
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from hardware.control_service import (
    classify_gpu_control_status,
    hardware_mutation_disabled_control_response,
    is_gpu_control_no_op,
    project_gpu_control_apply_result,
    snapshot_gpu_control_after,
    snapshot_gpu_control_before,
)
from hardware.control_snapshots import find_gpu_capabilities, find_gpu_entry
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding
from hardware.gpu_tuning.control_backend_selection import group_settings_by_control_backend
from hardware.gpu_tuning.control_operation_delivery import run_finalized_gpu_control_operation
from hardware.gpu_tuning.control_operation_finalization import (
    GPUControlSnapshotScope,
    execute_finalized_gpu_control_worker,
)
from hardware.gpu_tuning.control_saved_state_authority import control_state_digest
from hardware.gpu_tuning.control_worker_results import (
    GPU_CONTROL_WORKER_EXCEPTIONS,
)
from hardware.gpu_tuning.direct_apply import project_direct_gpu_apply_result
from hardware.gpu_tuning.direct_prepared_apply import (
    execute_gpu_settings_plan,
    prepare_gpu_settings_plan,
    rejected_gpu_settings_outcome,
)
from hardware.gpu_tuning.effective_control_state import build_apply_settings_for_modes
from hardware.gpu_tuning.setting_modes import derive_field_modes_from_settings
from hardware.validate import sanitize_settings

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols import HardwareGpuTuningProtocol, HardwareManagerProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.control_worker_results import GPUControlOperationOutcome
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies


__all__ = (
    "apply_snapshot_gpu_controls",
    "execute_snapshot_gpu_control",
)


async def apply_snapshot_gpu_controls(
    deps: GpuSettingsApplyDependencies,
    gpu_tuning: HardwareGpuTuningProtocol,
    hardware_manager: HardwareManagerProtocol,
    *,
    device_id: str,
    settings: JSONDict,
) -> JSONDict:
    capabilities = await gpu_tuning.get_gpu_capabilities()
    selected = get_capabilities_for_device(capabilities, device_id, None)
    if selected is None:
        raise ValidationError(f"GPU capabilities are unavailable for {device_id}.")
    binding = resolve_gpu_physical_binding(selected, [selected])
    if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
        raise ValidationError("GPU control has no unique physical target.")
    gpu_index = normalize_gpu_index(selected.get("index"))
    if gpu_index is None:
        gpu_index = normalize_gpu_index(selected.get("gpu_index"))
    if gpu_index is None:
        raise ValidationError("GPU snapshot control has no presentation index.")
    scope = GPUControlSnapshotScope(binding.device, str(gpu_index))
    operation_id = str(uuid4())
    payload = await run_finalized_gpu_control_operation(
        deps.control_operation_state,
        deps.delivery_dependencies,
        operation_id=operation_id,
        targets=scope,
        startup_resources=None,
        worker=partial(
            execute_snapshot_gpu_control,
            deps,
            gpu_tuning,
            hardware_manager,
            asyncio.get_running_loop(),
            scope,
            operation_id,
            device_id,
            copy.deepcopy(settings),
        ),
    )
    if payload.get("action") != "set":
        return {
            "action": "set",
            "device_id": device_id,
            "status": "failed",
            "before_snapshot": None,
            "normalized_settings": {},
            "apply_result": payload,
            "after_snapshot": None,
            "no_op": False,
            "failure_reason": payload.get("code"),
        }
    return {
        field: payload[field]
        for field in (
            "action",
            "device_id",
            "status",
            "before_snapshot",
            "normalized_settings",
            "apply_result",
            "after_snapshot",
            "no_op",
            "failure_reason",
        )
    }


def execute_snapshot_gpu_control(
    deps: GpuSettingsApplyDependencies,
    gpu_tuning: HardwareGpuTuningProtocol,
    hardware_manager: HardwareManagerProtocol,
    loop: asyncio.AbstractEventLoop,
    scope: GPUControlSnapshotScope,
    operation_id: str,
    device_id: str,
    settings: JSONDict,
    cancellation: CancellationTokenProtocol,
) -> GPUControlOperationOutcome:
    cancellation.raise_if_cancelled()
    if deps.runtime_flags.hardware_mutation_disabled:
        outcome = rejected_gpu_settings_outcome(
            scope.result_key,
            GPUControlPreflightRejection(
                "hardware_mutation_disabled", "Hardware mutation is disabled."
            ),
        )
        return replace(
            outcome,
            payload={**outcome.payload, **hardware_mutation_disabled_control_response(device_id)},
        )
    before_snapshot, capabilities = asyncio.run_coroutine_threadsafe(
        snapshot_gpu_control_before(hardware_manager, gpu_tuning), loop
    ).result()
    cancellation.raise_if_cancelled()
    before_gpu = find_gpu_entry(before_snapshot, device_id)
    if before_gpu is None:
        raise ValidationError(f"GPU device is not available: {device_id}")
    fresh = resolve_gpu_physical_binding(before_gpu, [before_gpu])
    if fresh.state != GPUPhysicalBindingState.BOUND or fresh.device is None:
        raise ValidationError("GPU before snapshot lost its unique physical target.")
    scope.require_target(fresh.device)
    capabilities_entry = find_gpu_capabilities(capabilities, before_gpu, device_id)
    try:
        normalized = sanitize_settings(settings, capabilities_entry)
        modes = derive_field_modes_from_settings(normalized)
        grouped = group_settings_by_control_backend(
            build_apply_settings_for_modes(normalized, modes), capabilities_entry
        )
    except GPUControlInputValidationError:
        raise
    except ValidationError as exception:
        raise GPUControlInputValidationError(exception.message) from exception
    user_fields = tuple(field for bucket in grouped.values() for field in bucket)
    with deps.storage.lock:
        intent = GPUControlCommitIntent(
            user_fields,
            control_state_digest(deps.storage.read_payload().payload, scope.target.device_id),
            None,
            None,
            None,
        )
    plan = prepare_gpu_settings_plan(
        deps,
        operation_id=operation_id,
        target=fresh.device,
        gpu_index=int(scope.result_key),
        capabilities=capabilities_entry,
        settings=normalized,
        field_modes=modes,
        commit_intent=intent,
        cancellation_token=cancellation,
    )
    if isinstance(plan, GPUControlPreflightRejection):
        outcome = rejected_gpu_settings_outcome(scope.result_key, plan)
    else:
        scope.require_target(plan.target)
        outcome = execute_finalized_gpu_control_worker(
            deps.delivery_dependencies.effects,
            partial(execute_gpu_settings_plan, deps, plan),
            cancellation,
            metadata_scope=None,
        )
    apply_result = project_direct_gpu_apply_result(
        device_id, int(scope.result_key), outcome.payload
    )
    after_snapshot: JSONDict
    try:
        after_snapshot = asyncio.run_coroutine_threadsafe(
            snapshot_gpu_control_after(hardware_manager, gpu_tuning, deps.logger), loop
        ).result()
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        failure = (
            ExceptionGroup(
                "GPU native completion and presentation failed.", [outcome.failure, exception]
            )
            if outcome.failure is not None and outcome.failure is not exception
            else exception
        )
        outcome = replace(outcome, failure=failure)
        after_snapshot = {"gpu": {"gpus": [], "by_device_id": {}}}
    after_gpu = find_gpu_entry(after_snapshot, device_id)
    no_op = is_gpu_control_no_op(apply_result)
    status, failure_reason = classify_gpu_control_status(
        apply_result=apply_result,
        after_gpu=after_gpu,
        no_op=no_op,
        logger=deps.logger,
    )
    payload = copy.deepcopy(outcome.payload)
    payload.update(
        action="set",
        device_id=device_id,
        status=status,
        before_snapshot=before_gpu,
        normalized_settings=normalized,
        apply_result=project_gpu_control_apply_result(apply_result),
        after_snapshot=after_gpu,
        no_op=no_op,
        failure_reason=failure_reason,
    )
    return replace(outcome, payload=payload)

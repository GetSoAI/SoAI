"""SoAI - Complete batch preparation and truthful partial GPU execution [backend/hardware/gpu_tuning/gpu_settings_sync_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import replace
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import (
    GPUControlCommitIntent,
    GPUControlPreflightRejection,
)
from core.hardware.gpu_control_types import GPUControlReduction
from core.hardware.gpu_operation_results import build_gpu_operation_error, build_gpu_result
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_slot_failures import GPUSettingOutOfRangeError
from core.types.json import JSONDict
from core.types.json_value import require_json_dict
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding
from hardware.gpu_tuning.control_backend_selection import group_settings_by_control_backend
from hardware.gpu_tuning.control_recovery_admission import require_distinct_control_targets
from hardware.gpu_tuning.control_saved_state_authority import control_state_digest
from hardware.gpu_tuning.control_worker_results import (
    GPU_CONTROL_WORKER_EXCEPTIONS,
    GPUControlOperationOutcome,
)
from hardware.gpu_tuning.direct_prepared_apply import (
    GPUPreparedSettingsPlan,
    execute_gpu_settings_plan,
    prepare_gpu_settings_plan,
    rejected_gpu_settings_outcome,
)
from hardware.gpu_tuning.effective_control_state import build_apply_settings_for_modes
from hardware.gpu_tuning.setting_modes import (
    derive_field_modes_from_settings,
    normalize_field_modes_for_settings,
)
from hardware.gpu_tuning.slot_capabilities import get_tuning_capabilities_for_services
from hardware.info_gpu import get_gpu_info
from hardware.validate import sanitize_settings

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies


__all__ = (
    "prepare_gpu_settings_batch",
    "sync_set_gpu_settings",
)


def prepare_gpu_settings_batch(
    deps: GpuSettingsApplyDependencies,
    *,
    operation_id: str,
    settings: JSONDict,
    field_modes: JSONDict | None,
    gpu_id: int | None,
    cancellation_token: CancellationTokenProtocol,
) -> tuple[GPUPreparedSettingsPlan, ...] | GPUControlOperationOutcome:
    settings, field_modes = copy.deepcopy((settings, field_modes))
    cancellation_token.raise_if_cancelled()
    inventory = get_gpu_info(
        deps.executor,
        detailed=False,
        cache_service=deps.gpu_services.gpu_info_cache_service,
        vendor_detection_service=deps.gpu_services.gpu_vendor_detection_service,
        nvidia_nvml_gate=deps.gpu_services.nvidia_nvml_gate,
        nvidia_capabilities_cache_service=deps.gpu_services.nvidia_capabilities_cache_service,
        adl_runtime=deps.gpu_services.adl_runtime,
    ).get("gpus")
    gpus = (
        [gpu for gpu in inventory if isinstance(gpu, dict)] if isinstance(inventory, list) else []
    )
    targets = (
        gpus
        if gpu_id is None
        else [gpu for gpu in gpus if normalize_gpu_index(gpu.get("index")) == gpu_id]
    )
    if not targets or not settings:
        code = "no_gpus" if not gpus else ("invalid_gpu_id" if not targets else "no_settings")
        return _zero_outcome(
            build_gpu_operation_error(
                code,
                "GPU request has no valid targets or settings.",
                details=(
                    {
                        "valid_gpu_ids": [
                            index
                            for gpu in gpus
                            if (index := normalize_gpu_index(gpu.get("index"))) is not None
                        ]
                    }
                    if code == "invalid_gpu_id"
                    else None
                ),
            )
        )
    capabilities = copy.deepcopy(
        get_tuning_capabilities_for_services(
            executor=deps.executor, gpu_services=deps.gpu_services, logger=deps.logger
        )
    )
    with deps.storage.lock:
        saved = copy.deepcopy(deps.storage.read_payload().payload)
    plans: list[GPUPreparedSettingsPlan] = []
    rejections: list[GPUControlPreflightRejection] = []
    results: JSONDict = {}
    for gpu in targets:
        cancellation_token.raise_if_cancelled()
        index = normalize_gpu_index(gpu.get("index"))
        device_id = gpu.get("device_id")
        key = str(index) if index is not None else str(len(results))
        results[key] = build_gpu_result(
            messages=["GPU target has not been attempted."], changed=False
        )
        try:
            if index is None or not isinstance(device_id, str) or not device_id:
                raise ValidationError("GPU request lacks its canonical device and public index.")
            binding = resolve_gpu_physical_binding(gpu, gpus)
            if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
                raise ValidationError("GPU target has no unique strong physical identity.")
            caps = get_capabilities_for_device(capabilities, device_id, index, selected_gpu=gpu)
            normalized = sanitize_settings(settings, caps)
            modes = (
                derive_field_modes_from_settings(normalized)
                if field_modes is None
                else normalize_field_modes_for_settings(normalized, field_modes)
            )
            grouped = group_settings_by_control_backend(
                build_apply_settings_for_modes(normalized, modes), caps
            )
            user_fields = tuple(field for bucket in grouped.values() for field in bucket)
            intent = GPUControlCommitIntent(
                user_fields, control_state_digest(saved, device_id), None, None, None
            )
            plan = prepare_gpu_settings_plan(
                deps,
                operation_id=f"{operation_id}:{device_id}",
                target=binding.device,
                gpu_index=index,
                capabilities=caps or {},
                settings=normalized,
                field_modes=modes,
                commit_intent=intent,
                cancellation_token=cancellation_token,
            )
            if isinstance(plan, GPUControlPreflightRejection):
                rejections.append(plan)
                results[key] = require_json_dict(
                    rejected_gpu_settings_outcome(key, plan).payload["gpus"],
                    label="GPU rejected results",
                )[key]
            else:
                plans.append(plan)
        except GPUSettingOutOfRangeError:
            raise
        except ValidationError as exception:
            rejection = GPUControlPreflightRejection("invalid_request_error", str(exception))
            rejections.append(rejection)
            results[key] = build_gpu_result(
                errors=["GPU request could not be prepared safely."], changed=False
            )
    if rejections:
        codes = {rejection.code for rejection in rejections}
        return replace(
            _zero_outcome(
                {
                    "success": False,
                    "gpus": results,
                    "changed": False,
                    "code": next(iter(codes)) if len(codes) == 1 else "invalid_request_error",
                }
            ),
            preflight_rejections=tuple(rejections),
        )
    require_distinct_control_targets(tuple(plan.target for plan in plans))
    return tuple(plans)


def sync_set_gpu_settings(
    deps: GpuSettingsApplyDependencies,
    plans: tuple[GPUPreparedSettingsPlan, ...],
    cancellation_token: CancellationTokenProtocol,
) -> GPUControlOperationOutcome:
    results: JSONDict = {
        plan.result_key: build_gpu_result(
            messages=["GPU target has not been attempted."], changed=False
        )
        for plan in plans
    }
    outcomes: list[GPUControlOperationOutcome] = []
    failure: Exception | None = None
    cancelled = False
    for plan in plans:
        try:
            cancellation_token.raise_if_cancelled()
            outcome = execute_gpu_settings_plan(deps, plan, cancellation_token)
            outcomes.append(outcome)
            entries = require_json_dict(outcome.payload["gpus"], label="GPU completed results")
            results[plan.result_key] = entries[plan.result_key]
            if outcome.failure is not None or outcome.cancelled:
                cancelled = outcome.cancelled
                break
        except TaskCancelledError:
            cancelled = True
            break
        except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
            failure = exception
            results[plan.result_key] = build_gpu_result(
                errors=["GPU application could not complete safely."]
            )
            outcomes.append(
                GPUControlOperationOutcome(
                    {"success": False},
                    (GPUControlReduction(None, True, False, False),),
                    False,
                    False,
                    exception,
                    False,
                    (),
                    (),
                    (),
                    None,
                    None,
                )
            )
            break
    failures = [outcome.failure for outcome in outcomes if outcome.failure is not None]
    if failures:
        failure = (
            failures[0]
            if len(failures) == 1
            else ExceptionGroup("GPU batch operation failed.", failures)
        )
    successful = (
        len(outcomes) == len(plans)
        and all(outcome.payload.get("success") is True for outcome in outcomes)
        and failure is None
        and not cancelled
    )
    receipts = tuple(
        outcome.dirty_marker_receipt
        for outcome in outcomes
        if outcome.dirty_marker_receipt is not None
    )
    payload: JSONDict = {"success": successful, "gpus": results}
    snapshots: JSONDict = {}
    for outcome in outcomes:
        if "committed_state_snapshots" in outcome.payload:
            snapshots.update(
                require_json_dict(
                    outcome.payload["committed_state_snapshots"], label="GPU committed snapshots"
                )
            )
    if snapshots:
        payload["committed_state_snapshots"] = snapshots
    if outcomes and all(
        outcome.payload.get("code") == "hardware_mutation_disabled" for outcome in outcomes
    ):
        payload["code"] = "hardware_mutation_disabled"
        payload["error"] = "Hardware mutation is disabled."
    return GPUControlOperationOutcome(
        payload,
        tuple(reduction for outcome in outcomes for reduction in outcome.reductions),
        any(outcome.metadata_changed for outcome in outcomes),
        any(outcome.persistence_uncertain for outcome in outcomes),
        failure,
        cancelled,
        tuple(result for outcome in outcomes for result in outcome.native_results),
        tuple(rejection for outcome in outcomes for rejection in outcome.preflight_rejections),
        tuple(ack for outcome in outcomes for ack in outcome.committed),
        receipts[-1] if receipts else None,
        None,
    )


def _zero_outcome(payload: JSONDict) -> GPUControlOperationOutcome:
    return GPUControlOperationOutcome(
        payload, (), False, False, None, False, (), (), (), None, None
    )

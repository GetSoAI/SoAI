"""SoAI - Direct GPU settings application helpers [backend/hardware/gpu_tuning/direct_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from core.concurrency.cancellation import CancellationToken
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import (
    GPUControlCommitIntent,
    GPUControlPreflightRejection,
)
from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_slot_failures import build_gpu_validation_failure
from core.logging.trace import get_logger
from core.types.json_value import is_json_value
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_inventory.physical_binding import (
    gpu_entry_accepts_device_id,
    resolve_gpu_physical_binding,
)
from hardware.gpu_tuning.control_backend_selection import group_settings_by_control_backend
from hardware.gpu_tuning.control_operation_delivery import run_finalized_gpu_control_operation
from hardware.gpu_tuning.control_saved_state_authority import control_state_digest
from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies
from hardware.gpu_tuning.direct_prepared_apply import (
    execute_gpu_settings_plan,
    prepare_gpu_settings_plan,
    rejected_gpu_settings_outcome,
)
from hardware.gpu_tuning.effective_control_state import build_apply_settings_for_modes
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.setting_modes import derive_field_modes_from_settings
from hardware.gpu_tuning.slot_capabilities import (
    async_get_tuning_capabilities,
    snapshot_tuning_inventory,
)
from hardware.gpu_tuning.slot_errors import (
    apply_failed_error,
    device_missing_error,
    gpu_index_error,
)
from hardware.validate import sanitize_settings

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("apply_gpu_settings_direct",)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.direct_apply"


async def apply_gpu_settings_direct(
    *,
    settings_deps: GpuSettingsApplyDependencies,
    dirty_flag_path: str,
    device_id: str,
    settings: JSONDict,
    capabilities_snapshot: JSONDict | None = None,
) -> JSONDict:
    deps = settings_deps
    if dirty_flag_path != deps.native_control_recovery.dependencies.dirty_flag_path:
        raise ValidationError("GPU direct request must use its actual marker authority.")
    if not isinstance(settings, dict) or not settings:
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload must be a non-empty mapping.",
            device_id=device_id,
        )
    capabilities = (
        capabilities_snapshot
        if isinstance(capabilities_snapshot, dict)
        else await async_get_tuning_capabilities(
            executor=deps.executor,
            gpu_services=deps.gpu_services,
            logger=deps.logger,
        )
    )

    if capabilities.get("success") is False:
        return build_gpu_operation_error(
            "device_unavailable",
            "GPU capability discovery is unavailable. Wait for recovery and retry.",
            device_id=device_id,
            changed=False,
        )

    def prepare_device(device_info: JSONDict, cap_entry: JSONDict) -> JSONDict:
        gpu_index = normalize_gpu_index(device_info.get("index"))
        if gpu_index is None:
            gpu_index = normalize_gpu_index(device_info.get("gpu_index"))
        if gpu_index is None:
            return gpu_index_error(device_id)
        try:
            sanitized = sanitize_settings(settings, cap_entry)
        except ValidationError as exception:
            return build_gpu_validation_failure(exception, device_id=device_id)
        return {
            "success": True,
            "gpu_index": gpu_index,
            "device_info": device_info,
            "capabilities": cap_entry,
            "sanitized": sanitized,
        }

    def prepare() -> JSONDict:
        cap_entry = get_capabilities_for_device(capabilities, device_id, None)
        if (
            isinstance(cap_entry, dict)
            and resolve_gpu_physical_binding(cap_entry, [cap_entry]).state
            == GPUPhysicalBindingState.BOUND
        ):
            prepared_from_caps = prepare_device(cap_entry, cap_entry)
            if prepared_from_caps.get("code") != "device_unavailable":
                return prepared_from_caps
        inventory = snapshot_tuning_inventory(
            executor=deps.executor,
            detailed_gpu_info=deps.detailed_gpu_info,
            gpu_services=deps.gpu_services,
        )
        if not (device_info := inventory.get(device_id)):
            return device_missing_error(device_id)
        if (gpu_index := normalize_gpu_index(device_info.get("gpu_index"))) is None:
            return gpu_index_error(device_id)
        cap_entry = get_capabilities_for_device(
            capabilities, device_id, gpu_index, selected_gpu=device_info
        )
        if not isinstance(cap_entry, dict):
            cap_entry = {}
        return prepare_device(device_info, cap_entry)

    prepared = await asyncio.to_thread(prepare)
    if not is_success_result(
        prepared,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.direct_apply.is_success_result",
        recover_message="Failed to parse GPU operation success flag (non-critical).",
    ):
        return prepared
    prepared_gpu_index = prepared.get("gpu_index")
    if not isinstance(prepared_gpu_index, int):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid gpu_index.",
            device_id=device_id,
        )
    prepared_sanitized = prepared.get("sanitized")
    if not isinstance(prepared_sanitized, dict):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid sanitized settings.",
            device_id=device_id,
        )
    prepared_device_info = prepared.get("device_info")
    if not isinstance(prepared_device_info, dict):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid device info.",
            device_id=device_id,
        )
    prepared_capabilities = prepared.get("capabilities")
    if not isinstance(prepared_capabilities, dict):
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU settings payload returned invalid capabilities.",
            device_id=device_id,
        )
    apply_result = await async_apply_prepared_gpu_settings(
        settings_deps,
        device_id=device_id,
        gpu_index=prepared_gpu_index,
        device_info=prepared_device_info,
        capabilities=prepared_capabilities,
        settings=prepared_sanitized,
    )
    return project_direct_gpu_apply_result(device_id, prepared_gpu_index, apply_result)


def project_direct_gpu_apply_result(
    device_id: str, gpu_index: int, apply_result: JSONDict
) -> JSONDict:
    if not is_success_result(
        apply_result,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.direct_apply.is_success_result",
        recover_message="Failed to parse GPU operation success flag (non-critical).",
    ):
        if apply_result.get("code") in {"gpu_activity_conflict", "gpu_control_preparation_failed"}:
            return apply_result
        failed = apply_failed_error(device_id, details=apply_result)
        if isinstance(apply_result.get("changed"), bool):
            failed["changed"] = apply_result["changed"]
        return failed
    result_entry: JSONValue | None = None
    gpus_value = apply_result.get("gpus")
    if isinstance(gpus_value, Mapping):
        result_entry = gpus_value.get(str(gpu_index))
    result: JSONDict = {
        "success": True,
        "device_id": device_id,
        "result": result_entry if is_json_value(result_entry) else None,
    }
    if isinstance(apply_result.get("changed"), bool):
        result["changed"] = apply_result["changed"]
    applied_at = apply_result.get("applied_at")
    if isinstance(applied_at, str):
        result["applied_at"] = applied_at
    return result


async def async_apply_prepared_gpu_settings(
    deps: GpuSettingsApplyDependencies,
    *,
    device_id: str,
    gpu_index: int,
    device_info: JSONDict,
    capabilities: JSONDict,
    settings: JSONDict,
    field_modes: JSONDict | None = None,
    commit_intent: GPUControlCommitIntent | None = None,
) -> JSONDict:
    device_info, capabilities, settings = copy.deepcopy((device_info, capabilities, settings))
    operation_id = str(uuid4())
    cancellation = CancellationToken(operation_id, owner="gpu-control-preparation")

    def cancel_preparation() -> None:
        cancellation.cancel("GPU preparation client disconnected.")

    binding = resolve_gpu_physical_binding(device_info, [device_info])
    if (
        not gpu_entry_accepts_device_id(device_info, device_id)
        or binding.state != GPUPhysicalBindingState.BOUND
        or binding.device is None
    ):
        return rejected_gpu_settings_outcome(
            str(gpu_index),
            GPUControlPreflightRejection(
                "device_unavailable", "GPU inventory has no unique strong physical target."
            ),
        ).payload
    modes = (
        derive_field_modes_from_settings(settings)
        if field_modes is None
        else copy.deepcopy(field_modes)
    )
    grouped = group_settings_by_control_backend(
        build_apply_settings_for_modes(settings, modes), capabilities
    )
    user_fields = tuple(field for bucket in grouped.values() for field in bucket)
    intent = commit_intent
    if intent is None:
        with deps.storage.lock:
            read = deps.storage.read_payload()
            intent = GPUControlCommitIntent(
                user_fields,
                control_state_digest(read.payload, binding.device.device_id),
                None,
                None,
                None,
            )
    plan = await run_joined_thread_call(
        partial(
            prepare_gpu_settings_plan,
            deps,
            operation_id=operation_id,
            target=binding.device,
            gpu_index=gpu_index,
            capabilities=copy.deepcopy(capabilities),
            settings=copy.deepcopy(settings),
            field_modes=modes,
            commit_intent=intent,
            cancellation_token=cancellation,
        ),
        task_name=f"gpu-control-preparation:{operation_id}",
        retain_resources_until_complete=True,
        on_cancel=cancel_preparation,
    )
    if isinstance(plan, GPUControlPreflightRejection):
        return rejected_gpu_settings_outcome(str(gpu_index), plan).payload
    return await run_finalized_gpu_control_operation(
        deps.control_operation_state,
        deps.delivery_dependencies,
        operation_id=operation_id,
        targets=(plan.finalization_target,),
        startup_resources=None,
        worker=partial(execute_gpu_settings_plan, deps, plan),
    )

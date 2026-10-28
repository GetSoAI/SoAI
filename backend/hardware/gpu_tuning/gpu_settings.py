"""SoAI - GPU settings application [backend/hardware/gpu_tuning/gpu_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from core.concurrency.cancellation import CancellationToken
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from hardware.gpu_tuning.control_operation_delivery import (
    GPUControlDeliveryDependencies,
    run_finalized_gpu_control_operation,
)
from hardware.gpu_tuning.control_operations import GPUControlOperationState
from hardware.gpu_tuning.control_worker_results import GPUControlOperationOutcome
from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies
from hardware.gpu_tuning.gpu_settings_sync_apply import (
    prepare_gpu_settings_batch,
    sync_set_gpu_settings,
)
from hardware.gpu_tuning.native_control_recovery import NativeControlRecovery
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "async_set_gpu_settings",
    "build_gpu_settings_apply_dependencies",
    "sync_set_gpu_settings",
)


def build_gpu_settings_apply_dependencies(
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    nvidia_settings_controller: NvidiaSettingsController | None,
    gpu_services: GpuServiceDependencies,
    native_control_recovery: NativeControlRecovery,
    control_operation_state: GPUControlOperationState,
    delivery_dependencies: GPUControlDeliveryDependencies,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> GpuSettingsApplyDependencies:
    return GpuSettingsApplyDependencies(
        executor=executor,
        logger=logger,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        nvidia_settings_controller=nvidia_settings_controller,
        gpu_services=gpu_services,
        native_control_recovery=native_control_recovery,
        control_operation_state=control_operation_state,
        delivery_dependencies=delivery_dependencies,
        runtime_flags=runtime_flags,
    )


async def async_set_gpu_settings(
    deps: GpuSettingsApplyDependencies,
    *,
    gpu_id: int | None = None,
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None = None,
) -> JSONDict:
    operation_id = str(uuid4())
    cancellation = CancellationToken(operation_id, owner="gpu-control-preparation")

    def cancel_preparation() -> None:
        cancellation.cancel("GPU preparation client disconnected.")

    field_modes_payload = copy.deepcopy(dict(field_modes)) if field_modes is not None else None
    plans = await run_joined_thread_call(
        partial(
            prepare_gpu_settings_batch,
            deps,
            operation_id=operation_id,
            gpu_id=gpu_id,
            settings=copy.deepcopy(dict(settings)),
            field_modes=field_modes_payload,
            cancellation_token=cancellation,
        ),
        task_name=f"gpu-control-preparation:{operation_id}",
        retain_resources_until_complete=True,
        on_cancel=cancel_preparation,
    )
    if isinstance(plans, GPUControlOperationOutcome):
        return plans.payload
    return await run_finalized_gpu_control_operation(
        deps.control_operation_state,
        deps.delivery_dependencies,
        operation_id=operation_id,
        targets=tuple(plan.finalization_target for plan in plans),
        startup_resources=None,
        worker=partial(sync_set_gpu_settings, deps, plans),
    )

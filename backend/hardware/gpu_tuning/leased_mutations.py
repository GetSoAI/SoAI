"""SoAI - GPU tuning lease-protected public mutations [backend/hardware/gpu_tuning/leased_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import uuid
from collections.abc import Callable, Mapping
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ValidationError
from core.hardware.types import GPUSettingsOutcome
from hardware.gpu_tuning.control_operation_delivery import run_finalized_gpu_control_operation
from hardware.gpu_tuning.control_worker_results import GPUControlOperationOutcome
from hardware.gpu_tuning.mutation_leases import (
    GPUControlMetadataScope,
)
from hardware.gpu_tuning.mutation_policy import (
    hardware_mutation_disabled_outcome,
    hardware_mutation_disabled_payload,
)
from hardware.gpu_tuning.service_capability_refresh import (
    refresh_capabilities_if_gpu_apply_changed,
)
from hardware.gpu_tuning.service_mutations import (
    apply_gpu_settings_direct_for_service,
    process_gpu_settings_request_for_service,
)
from hardware.gpu_tuning.slot_apply_async import async_execute_slot_apply
from hardware.gpu_tuning.slot_boot_toggle import sync_toggle_gpu_slot_boot
from hardware.gpu_tuning.slot_capabilities import snapshot_tuning_inventory
from hardware.gpu_tuning.slot_errors import device_missing_error
from hardware.gpu_tuning.slot_writes import sync_clear_gpu_slot, sync_store_gpu_slot
from hardware.presets.inventory_snapshot import resolve_inventory_device_id

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict, JSONValue
    from hardware.gpu_tuning.internal_protocols import (
        HardwareGpuTuningMutationServiceProtocol,
    )

__all__ = (
    "apply_gpu_settings_direct_with_lease",
    "apply_gpu_slot_with_lease",
    "clear_gpu_slot_with_lease",
    "process_gpu_settings_request_with_lease",
    "store_gpu_slot_with_lease",
    "toggle_gpu_slot_boot_with_lease",
)


async def store_gpu_slot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None,
    apply_at_boot: bool | None,
) -> JSONDict:
    settings_payload, modes = copy.deepcopy(dict(settings)), copy.deepcopy(field_modes)
    return await _run_metadata_mutation(
        service,
        device_id,
        lambda canonical: sync_store_gpu_slot(
            executor=service.executor,
            storage=service.storage,
            detailed_gpu_info=service.detailed_gpu_info,
            logger=service.logger,
            device_id=canonical,
            slot=slot,
            settings=settings_payload,
            field_modes=modes,
            apply_at_boot=apply_at_boot,
            gpu_services=service.gpu_services,
        ),
        require_enabled=True,
    )


async def clear_gpu_slot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
) -> JSONDict:
    return await _run_metadata_mutation(
        service,
        device_id,
        lambda canonical: sync_clear_gpu_slot(
            executor=service.executor,
            storage=service.storage,
            recovery=service.gpu_settings_apply_deps.native_control_recovery,
            detailed_gpu_info=service.detailed_gpu_info,
            device_id=canonical,
            slot=slot,
            gpu_services=service.gpu_services,
        ),
        require_enabled=False,
    )


async def toggle_gpu_slot_boot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
    enabled: bool,
) -> JSONDict:
    return await _run_metadata_mutation(
        service,
        device_id,
        lambda canonical: sync_toggle_gpu_slot_boot(
            executor=service.executor,
            storage=service.storage,
            detailed_gpu_info=service.detailed_gpu_info,
            device_id=canonical,
            slot=slot,
            enabled=enabled,
            gpu_services=service.gpu_services,
        ),
        require_enabled=True,
    )


async def apply_gpu_slot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
    apply_at_boot: bool | None,
) -> JSONDict:
    if service.runtime_flags.hardware_mutation_disabled:
        return hardware_mutation_disabled_payload()
    result = await async_execute_slot_apply(
        settings_deps=service.gpu_settings_apply_deps,
        dirty_flag_path=service.dirty_flag_path,
        event_bus=service.event_bus,
        main_loop=service.main_loop,
        cancellation_binder=service.cancellation_binder,
        finalizer_tracker=service.finalizer_tracker,
        device_id=device_id,
        slot=slot,
        apply_at_boot=apply_at_boot,
    )
    await refresh_capabilities_if_gpu_apply_changed(service, result)
    return result


async def apply_gpu_settings_direct_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    settings: JSONDict,
) -> JSONDict:
    if service.runtime_flags.hardware_mutation_disabled:
        return hardware_mutation_disabled_payload()
    return await apply_gpu_settings_direct_for_service(service, device_id, settings)


async def process_gpu_settings_request_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    payload: Mapping[str, JSONValue],
) -> GPUSettingsOutcome:
    if service.runtime_flags.hardware_mutation_disabled:
        return hardware_mutation_disabled_outcome()
    return await process_gpu_settings_request_for_service(service, payload)


async def _run_metadata_mutation(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    operation: Callable[[str], JSONDict],
    *,
    require_enabled: bool,
) -> JSONDict:
    if require_enabled and service.runtime_flags.hardware_mutation_disabled:
        return hardware_mutation_disabled_payload()
    inventory = await run_joined_thread_call(
        partial(
            snapshot_tuning_inventory,
            executor=service.executor,
            detailed_gpu_info=service.detailed_gpu_info,
            gpu_services=service.gpu_services,
        ),
        task_name="gpu-slot-metadata-inventory",
        retain_resources_until_complete=True,
    )
    canonical = resolve_inventory_device_id(inventory, device_id)
    if canonical is None:
        return device_missing_error(device_id)
    deps = service.gpu_settings_apply_deps
    return await run_finalized_gpu_control_operation(
        deps.control_operation_state,
        deps.delivery_dependencies,
        operation_id=str(uuid.uuid4()),
        targets=GPUControlMetadataScope((canonical,)),
        startup_resources=None,
        worker=partial(_execute_metadata_mutation, service, canonical, operation, require_enabled),
    )


def _execute_metadata_mutation(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    operation: Callable[[str], JSONDict],
    require_enabled: bool,
    cancellation: CancellationTokenProtocol,
) -> GPUControlOperationOutcome:
    cancellation.raise_if_cancelled()
    result = (
        hardware_mutation_disabled_payload()
        if require_enabled and service.runtime_flags.hardware_mutation_disabled
        else operation(device_id)
    )
    if result.get("success") is True and result.get("device_id") != device_id:
        raise ValidationError("GPU metadata result changed its canonical lease target.")
    return GPUControlOperationOutcome(
        result,
        (),
        result.get("success") is True,
        False,
        None,
        False,
        (),
        (),
        (),
        None,
        None,
    )

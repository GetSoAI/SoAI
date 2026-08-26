"""SoAI - GPU tuning lease-protected public mutations [backend/hardware/gpu_tuning/leased_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.types import GPUSettingsOutcome
from hardware.gpu_tuning.events import emit_mutation_events
from hardware.gpu_tuning.mutation_leases import (
    gpu_mutation_conflict_payload,
    run_json_with_gpu_mutation_lease,
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
from hardware.gpu_tuning.slot_writes import sync_clear_gpu_slot, sync_store_gpu_slot

if TYPE_CHECKING:
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

OWNER_ID = "gpu_tuning"


async def store_gpu_slot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None,
    apply_at_boot: bool | None,
) -> JSONDict:
    settings_payload = dict(settings)

    async def operation() -> JSONDict:
        async with service.gpu_operation_lock:
            if service.runtime_flags.hardware_mutation_disabled:
                return hardware_mutation_disabled_payload()
            result = await asyncio.to_thread(
                sync_store_gpu_slot,
                executor=service.executor,
                storage=service.storage,
                detailed_gpu_info=service.detailed_gpu_info,
                logger=service.logger,
                device_id=device_id,
                slot=slot,
                settings=settings_payload,
                field_modes=field_modes,
                apply_at_boot=apply_at_boot,
                gpu_services=service.gpu_services,
            )
        _emit_mutation_events(service, result, emit_boot_on_success=False)
        return result

    return await run_json_with_gpu_mutation_lease(
        activity_registry=service.activity_registry,
        device_id=device_id,
        owner_id=OWNER_ID,
        operation=operation,
    )


async def clear_gpu_slot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
) -> JSONDict:
    async def operation() -> JSONDict:
        async with service.gpu_operation_lock:
            result = await asyncio.to_thread(
                sync_clear_gpu_slot,
                executor=service.executor,
                storage=service.storage,
                gpu_slots_path=service.gpu_slots_path,
                detailed_gpu_info=service.detailed_gpu_info,
                logger=service.logger,
                device_id=device_id,
                slot=slot,
                gpu_services=service.gpu_services,
            )
        _emit_mutation_events(service, result, emit_boot_on_success=False)
        return result

    return await run_json_with_gpu_mutation_lease(
        activity_registry=service.activity_registry,
        device_id=device_id,
        owner_id=OWNER_ID,
        operation=operation,
    )


async def toggle_gpu_slot_boot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
    enabled: bool,
) -> JSONDict:
    async def operation() -> JSONDict:
        async with service.gpu_operation_lock:
            if service.runtime_flags.hardware_mutation_disabled:
                return hardware_mutation_disabled_payload()
            result = await asyncio.to_thread(
                sync_toggle_gpu_slot_boot,
                executor=service.executor,
                storage=service.storage,
                detailed_gpu_info=service.detailed_gpu_info,
                device_id=device_id,
                slot=slot,
                enabled=enabled,
                gpu_services=service.gpu_services,
            )
        _emit_mutation_events(service, result, emit_boot_on_success=True)
        return result

    return await run_json_with_gpu_mutation_lease(
        activity_registry=service.activity_registry,
        device_id=device_id,
        owner_id=OWNER_ID,
        operation=operation,
    )


async def apply_gpu_slot_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    slot: str | int,
    apply_at_boot: bool | None,
) -> JSONDict:
    async def operation() -> JSONDict:
        async with service.gpu_operation_lock:
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

    return await run_json_with_gpu_mutation_lease(
        activity_registry=service.activity_registry,
        device_id=device_id,
        owner_id=OWNER_ID,
        operation=operation,
    )


async def apply_gpu_settings_direct_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    device_id: str,
    settings: JSONDict,
) -> JSONDict:
    async def operation() -> JSONDict:
        async with service.gpu_operation_lock:
            if service.runtime_flags.hardware_mutation_disabled:
                return hardware_mutation_disabled_payload()
            return await apply_gpu_settings_direct_for_service(service, device_id, settings)

    return await run_json_with_gpu_mutation_lease(
        activity_registry=service.activity_registry,
        device_id=device_id,
        owner_id=OWNER_ID,
        operation=operation,
    )


async def process_gpu_settings_request_with_lease(
    service: HardwareGpuTuningMutationServiceProtocol,
    payload: Mapping[str, JSONValue],
) -> GPUSettingsOutcome:
    device_id_value = payload.get("device_id")
    if not isinstance(device_id_value, str) or not device_id_value.strip():
        async with service.gpu_operation_lock:
            if service.runtime_flags.hardware_mutation_disabled:
                return hardware_mutation_disabled_outcome()
            return await process_gpu_settings_request_for_service(service, payload)
    device_id = device_id_value.strip()
    acquire = await service.activity_registry.acquire(
        device_id=device_id,
        activity_type="mutation",
        owner_id=OWNER_ID,
        conflict_reason="gpu_tuning_active",
    )
    if acquire.conflict is not None:
        conflict_payload = gpu_mutation_conflict_payload(acquire.conflict)
        return GPUSettingsOutcome(
            success=False,
            status_code=409,
            payload=conflict_payload,
            audit_action="APPLY_GPU_SETTINGS_DIRECT",
            audit_target=f"gpu_device:{device_id}",
            audit_details={"device_id": device_id, "fields": []},
            error_type="gpu_activity_conflict",
            error_message="GPU activity is already running for this device.",
            error_detail=conflict_payload,
        )
    if acquire.lease is None:
        raise ValidationError("GPU mutation activity lease acquisition failed.")
    try:
        async with service.gpu_operation_lock:
            if service.runtime_flags.hardware_mutation_disabled:
                return hardware_mutation_disabled_outcome()
            return await process_gpu_settings_request_for_service(service, payload)
    finally:
        await service.activity_registry.release(
            device_id=acquire.lease.device_id,
            lease_id=acquire.lease.lease_id,
        )


def _emit_mutation_events(
    service: HardwareGpuTuningMutationServiceProtocol,
    result: JSONDict,
    *,
    emit_boot_on_success: bool,
) -> None:
    emit_mutation_events(
        executor=service.executor,
        event_bus=service.event_bus,
        main_loop=service.main_loop,
        cancellation_binder=service.cancellation_binder,
        finalizer_tracker=service.finalizer_tracker,
        logger=service.logger,
        result=result,
        emit_boot_on_success=emit_boot_on_success,
        gpu_services=service.gpu_services,
    )

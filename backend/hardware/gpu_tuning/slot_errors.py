"""SoAI - GPU slot operation errors and helpers [backend/hardware/gpu_tuning/slot_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from hardware.control.profiles import default_boot_payload, normalize_slot_identifier
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_capabilities import snapshot_tuning_inventory
from hardware.gpu_tuning.slot_payload import (
    SlotPayloadDependencies,
    build_slot_payload_dependencies,
)
from hardware.presets.slot_payload_loading import load_gpu_slots_payload_unlocked

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "OPERATION_HARDWARE_GPU_TUNING_SLOT_ERRORS_TRY_REMOVE_SLOTS_FILE",
    "SlotOperationContext",
    "apply_failed_error",
    "device_missing_error",
    "devices",
    "empty_device_entry",
    "gpu_index_error",
    "load_locked_slot_operation_context_for_device",
    "load_slot_operation_context",
    "load_slot_operation_context_for_device",
    "load_slot_operation_context_or_error",
    "resolve_slot_identifier_or_error",
    "resolve_slot_payload_dependencies_and_identifier_or_error",
    "slot_empty_error",
    "slot_invalid_error",
    "slot_unchanged_error",
    "try_remove_slots_file",
)

OPERATION_HARDWARE_GPU_TUNING_SLOT_ERRORS_TRY_REMOVE_SLOTS_FILE = (
    "hardware.gpu_tuning.slot_errors.try_remove_slots_file"
)


def devices(payload: JSONDict) -> JSONDict:
    if not isinstance(payload, dict):
        return {}
    devices_payload = payload.get("devices")
    return devices_payload if isinstance(devices_payload, dict) else {}


def slot_invalid_error(slot: JSONValue) -> JSONDict:
    return build_gpu_operation_error(
        "invalid_slot",
        "Slot identifier must be between 1 and 3.",
        slot=slot,
    )


def resolve_slot_identifier_or_error(slot: str | int) -> str | JSONDict:
    slot_id = normalize_slot_identifier(slot)
    if not slot_id:
        return slot_invalid_error(slot)
    return slot_id


def resolve_slot_payload_dependencies_and_identifier_or_error(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    slot: str | int,
    gpu_services: GpuServiceDependencies,
) -> tuple[str, SlotPayloadDependencies] | JSONDict:
    slot_id_or_error = resolve_slot_identifier_or_error(slot)
    if isinstance(slot_id_or_error, dict):
        return slot_id_or_error
    return (
        slot_id_or_error,
        build_slot_payload_dependencies(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            logger=logger,
            gpu_services=gpu_services,
        ),
    )


def device_missing_error(device_id: str) -> JSONDict:
    return build_gpu_operation_error(
        "device_not_found",
        "GPU device was not found.",
        device_id=device_id,
    )


def slot_empty_error(
    device_id: str,
    slot_id: str,
    message: str = "Requested slot does not contain settings.",
) -> JSONDict:
    return build_gpu_operation_error(
        "slot_empty",
        message,
        device_id=device_id,
        slot=slot_id,
    )


def slot_unchanged_error(
    device_id: str,
    slot_id: str,
    message: str = "GPU slot already contains identical settings.",
) -> JSONDict:
    return build_gpu_operation_error(
        "slot_unchanged",
        message,
        device_id=device_id,
        slot=slot_id,
    )


def gpu_index_error(device_id: str) -> JSONDict:
    return build_gpu_operation_error(
        "device_unavailable",
        "GPU index for the device is invalid.",
        device_id=device_id,
    )


def apply_failed_error(
    device_id: str,
    slot_id: str | None = None,
    details: JSONValue = None,
) -> JSONDict:
    details_payload = details if isinstance(details, dict) else None
    return build_gpu_operation_error(
        "apply_failed",
        ("Failed to apply GPU slot settings." if slot_id else "Failed to apply GPU settings."),
        device_id=device_id,
        slot=slot_id,
        details=details_payload,
    )


def empty_device_entry(info: JSONDict) -> JSONDict:
    return {
        "gpu_index": info.get("gpu_index"),
        "name": info.get("name"),
        "slots": {},
        "boot": default_boot_payload(),
    }


def try_remove_slots_file(
    *,
    gpu_slots_path: str,
    logger: TraceLogger,
    operation_context: str,
) -> None:
    try:
        os.remove(gpu_slots_path)
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to remove GPU slots file",
            operation=OPERATION_HARDWARE_GPU_TUNING_SLOT_ERRORS_TRY_REMOVE_SLOTS_FILE,
            details={"gpu_slots_path": gpu_slots_path, "operation_context": operation_context},
            level="warning",
        )


@dataclass(frozen=True, slots=True)
class SlotOperationContext:
    inventory: dict[str, JSONDict]
    payload: JSONDict
    entry: JSONDict | None
    error: JSONDict | None = None


def load_slot_operation_context(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    gpu_services: GpuServiceDependencies,
) -> SlotOperationContext:
    inventory = snapshot_tuning_inventory(
        executor=executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
    )
    if device_id not in inventory:
        return SlotOperationContext(
            inventory=inventory,
            payload={},
            entry=None,
            error=device_missing_error(device_id),
        )
    payload = load_gpu_slots_payload_unlocked(
        storage,
        inventory=inventory,
        prune=True,
        allow_create=False,
    )
    entry_raw = devices(payload).get(device_id)
    entry = entry_raw if isinstance(entry_raw, dict) else None
    return SlotOperationContext(
        inventory=inventory,
        payload=payload,
        entry=entry,
        error=None,
    )


def load_slot_operation_context_for_device(
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    gpu_services: GpuServiceDependencies,
) -> SlotOperationContext:
    return load_slot_operation_context(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        device_id=device_id,
        gpu_services=gpu_services,
    )


def load_locked_slot_operation_context_for_device(
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    gpu_services: GpuServiceDependencies,
) -> SlotOperationContext:
    with storage.lock:
        return load_slot_operation_context_for_device(
            executor,
            storage,
            detailed_gpu_info,
            device_id,
            gpu_services,
        )


def load_slot_operation_context_or_error(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    gpu_services: GpuServiceDependencies,
) -> tuple[SlotOperationContext, JSONDict | None]:
    context = load_slot_operation_context(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        device_id=device_id,
        gpu_services=gpu_services,
    )
    return (context, context.error)

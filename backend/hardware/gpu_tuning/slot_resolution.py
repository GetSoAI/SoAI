"""SoAI - GPU slot resolution flow [backend/hardware/gpu_tuning/slot_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.gpu_tuning.slot_errors import (
    resolve_slot_payload_dependencies_and_identifier_or_error,
)
from hardware.gpu_tuning.slot_payload import (
    get_capabilities_and_inventory,
    load_inventory_and_payload,
)

if TYPE_CHECKING:
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
    from hardware.gpu_tuning.slot_payload import SlotPayloadDependencies

__all__ = (
    "load_locked_slot_inventory_payload_or_error",
    "load_preview_slot_inventory_payload_or_error",
    "load_slot_capabilities_inventory_payload_or_error",
    "load_slot_inventory_payload_or_error",
)


def load_slot_inventory_payload_or_error(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    slot: str | int,
    gpu_services: GpuServiceDependencies,
    allow_create: bool,
) -> tuple[str, SlotPayloadDependencies, dict[str, JSONDict], JSONDict] | JSONDict:
    resolved = resolve_slot_payload_dependencies_and_identifier_or_error(
        slot=slot,
        executor=executor,
        logger=logger,
        storage=storage,
        gpu_services=gpu_services,
        detailed_gpu_info=detailed_gpu_info,
    )
    if isinstance(resolved, dict):
        return resolved
    slot_id, deps = resolved
    inventory, payload = load_inventory_and_payload(deps, allow_create=allow_create)
    return (slot_id, deps, inventory, payload)


def load_locked_slot_inventory_payload_or_error(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    slot: str | int,
    gpu_services: GpuServiceDependencies,
    allow_create: bool,
) -> tuple[str, SlotPayloadDependencies, dict[str, JSONDict], JSONDict] | JSONDict:
    with storage.lock:
        return load_slot_inventory_payload_or_error(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            logger=logger,
            slot=slot,
            gpu_services=gpu_services,
            allow_create=allow_create,
        )


def load_preview_slot_inventory_payload_or_error(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    slot: str | int,
    gpu_services: GpuServiceDependencies,
) -> tuple[str, SlotPayloadDependencies, dict[str, JSONDict], JSONDict] | JSONDict:
    return load_locked_slot_inventory_payload_or_error(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        logger=logger,
        slot=slot,
        gpu_services=gpu_services,
        allow_create=True,
    )


def load_slot_capabilities_inventory_payload_or_error(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    slot: str | int,
    gpu_services: GpuServiceDependencies,
    allow_create: bool,
) -> tuple[str, SlotPayloadDependencies, JSONDict, dict[str, JSONDict], JSONDict] | JSONDict:
    resolved = resolve_slot_payload_dependencies_and_identifier_or_error(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        logger=logger,
        slot=slot,
        gpu_services=gpu_services,
    )
    if isinstance(resolved, dict):
        return resolved
    slot_id, deps = resolved
    capabilities, inventory, payload = get_capabilities_and_inventory(
        deps,
        allow_create=allow_create,
    )
    return (slot_id, deps, capabilities, inventory, payload)

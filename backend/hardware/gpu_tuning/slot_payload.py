"""SoAI - GPU slot inventory and payload loading helpers [backend/hardware/gpu_tuning/slot_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_capabilities import (
    get_tuning_capabilities_for_services,
    snapshot_tuning_inventory,
)
from hardware.presets.slot_payload_loading import (
    snapshot_inventory_and_load_slots_payload,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "SlotInventoryObservation",
    "SlotPayloadDependencies",
    "build_slot_payload_dependencies",
    "get_capabilities_and_inventory",
    "load_inventory_and_payload",
    "load_locked_devices_payload",
    "load_locked_payload",
    "observe_locked_slot_inventory",
)


@dataclass(frozen=True, slots=True)
class SlotInventoryObservation:
    inventory: dict[str, JSONDict]
    payload: JSONDict
    nvidia_inventory_available: bool


@dataclass(frozen=True, slots=True)
class SlotPayloadDependencies:
    executor: CommandExecutorProtocol
    storage: GpuSlotStorageManagerProtocol
    logger: TraceLogger
    detailed_gpu_info: bool
    gpu_services: GpuServiceDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SlotPayloadDependencies",
            detailed_gpu_info=self.detailed_gpu_info,
            executor=self.executor,
            gpu_services=self.gpu_services,
            logger=self.logger,
            storage=self.storage,
        )


def build_slot_payload_dependencies(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
) -> SlotPayloadDependencies:
    return SlotPayloadDependencies(
        executor=executor,
        storage=storage,
        logger=logger,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
    )


def load_inventory_and_payload(
    deps: SlotPayloadDependencies,
    *,
    prune: bool = True,
    allow_create: bool,
) -> tuple[dict[str, JSONDict], JSONDict]:
    observation = observe_locked_slot_inventory(
        executor=deps.executor,
        storage=deps.storage,
        detailed_gpu_info=deps.detailed_gpu_info,
        gpu_services=deps.gpu_services,
        prune=prune,
        allow_create=allow_create,
    )
    return (observation.inventory, observation.payload)


def observe_locked_slot_inventory(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
    prune: bool = True,
    allow_create: bool,
) -> SlotInventoryObservation:
    inventory = snapshot_tuning_inventory(
        executor=executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
    )
    nvidia_inventory_available = (
        gpu_services.nvidia_capabilities_cache_service.inventory_available()
    )
    inventory_snapshot, payload = snapshot_inventory_and_load_slots_payload(
        storage,
        executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_info_cache_service=gpu_services.gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_services.gpu_vendor_detection_service,
        nvidia_nvml_gate=gpu_services.nvidia_nvml_gate,
        nvidia_capabilities_cache_service=gpu_services.nvidia_capabilities_cache_service,
        nvidia_inventory_available=nvidia_inventory_available,
        prune=prune,
        allow_create=allow_create,
        inventory=inventory,
    )
    return SlotInventoryObservation(
        inventory=inventory_snapshot,
        payload=payload,
        nvidia_inventory_available=nvidia_inventory_available,
    )


def load_locked_devices_payload(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
    prune: bool = True,
    allow_create: bool,
) -> JSONDict:
    observation = observe_locked_slot_inventory(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
        prune=prune,
        allow_create=allow_create,
    )
    devices_payload = observation.payload.get("devices")
    return devices_payload if isinstance(devices_payload, dict) else {}


def load_locked_payload(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
    allow_create: bool,
) -> JSONDict:
    observation = observe_locked_slot_inventory(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
        allow_create=allow_create,
    )
    return observation.payload


def get_capabilities_and_inventory(
    deps: SlotPayloadDependencies,
    *,
    allow_create: bool,
) -> tuple[JSONDict, dict[str, JSONDict], JSONDict]:
    capabilities = get_tuning_capabilities_for_services(
        executor=deps.executor,
        gpu_services=deps.gpu_services,
        logger=deps.logger,
    )
    inventory, payload = load_inventory_and_payload(deps, allow_create=allow_create)
    return (capabilities, inventory, payload)

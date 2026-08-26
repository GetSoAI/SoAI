"""SoAI - GPU capabilities enrichment with slot state [backend/hardware/gpu_tuning/capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.hardware.protocols import GpuSlotStorageManagerProtocol, NvmlGateProtocol
from core.logging.protocols import TraceLogger
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_payload import load_locked_devices_payload
from hardware.gpu_tuning.slot_state import build_live_state
from hardware.vendors.nvidia.smi import NvidiaSettingsController

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "create_nvidia_settings_controller",
    "enrich_gpu_capabilities_with_slots",
)


def _apply_live_state(cap_entry: JSONDict, live_state: JSONDict) -> None:
    cap_entry.update(live_state)
    cap_entry.pop("live", None)
    cap_entry["live"] = live_state


def create_nvidia_settings_controller(
    controller_logger: TraceLogger,
    nvml_gate: NvmlGateProtocol,
) -> NvidiaSettingsController | None:
    if not (nvml_gate.runtime_platform.is_linux and nvml_gate.nvidia_settings_available):
        return None
    controller = NvidiaSettingsController(controller_logger=controller_logger)
    controller_logger.trace("nvidia-settings controller initialized for Linux NVIDIA GPU control")
    return controller


def enrich_gpu_capabilities_with_slots(
    executor: CommandExecutorProtocol,
    capabilities: JSONDict,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    if not isinstance(capabilities, dict):
        return capabilities
    raw_gpus = capabilities.get("gpus")
    if not isinstance(raw_gpus, dict):
        return capabilities
    with storage.lock:
        devices_payload = load_locked_devices_payload(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            gpu_services=gpu_services,
            allow_create=True,
        )
    for index, cap_entry in list(raw_gpus.items()):
        if not isinstance(cap_entry, dict):
            continue
        device_id_raw = cap_entry.get("device_id")
        device_id = str(device_id_raw) if device_id_raw is not None else f"gpu-index-{index}"
        slot_entry_raw = (
            devices_payload.get(device_id) if isinstance(devices_payload, dict) else None
        )
        slot_entry = slot_entry_raw if isinstance(slot_entry_raw, dict) else None
        live_state = build_live_state(device_id, slot_entry, cap_entry)
        _apply_live_state(cap_entry, live_state)
        by_device_id = capabilities.get("gpus_by_device_id")
        if not isinstance(by_device_id, dict):
            continue
        device_entry = by_device_id.get(device_id)
        if isinstance(device_entry, dict) and device_entry is not cap_entry:
            _apply_live_state(device_entry, copy.deepcopy(live_state))
    return capabilities

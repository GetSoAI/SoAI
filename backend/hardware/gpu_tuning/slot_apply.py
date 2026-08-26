"""SoAI - GPU slot application persistence helpers [backend/hardware/gpu_tuning/slot_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from hardware.control.profiles import compute_slot_signature
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.boot_state import (
    boot_enabled,
    boot_payload_from_value,
    disabled_boot_payload,
    pending_enabled_boot_payload,
)
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.setting_modes import field_modes_mapping_or_none
from hardware.gpu_tuning.slot_errors import (
    devices,
    gpu_index_error,
    slot_empty_error,
)
from hardware.gpu_tuning.slot_operation_preparation import prepare_slot_apply_operation
from hardware.gpu_tuning.slot_payload import load_locked_payload
from hardware.presets.slot_mutations import record_slot_application_unlocked

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "sync_finalize_slot_apply",
    "sync_prepare_slot_apply",
)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.slot_apply"


def sync_prepare_slot_apply(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    slot: str | int,
    apply_at_boot: bool | None,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    prepared = prepare_slot_apply_operation(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        device_id=device_id,
        slot=slot,
        apply_at_boot=apply_at_boot,
        gpu_services=gpu_services,
    )
    if isinstance(prepared, dict):
        return prepared
    slot_id = prepared.slot_id
    apply_flag = prepared.apply_flag
    context = prepared.context
    entry = context.entry
    slots_val = entry.get("slots") if isinstance(entry, dict) else None
    slots_dict = slots_val if isinstance(slots_val, dict) else {}
    slot_entry = slots_dict.get(slot_id)
    if not (
        isinstance(entry, dict)
        and isinstance(slot_entry, dict)
        and isinstance((settings := slot_entry.get("settings")), dict)
        and settings
    ):
        return slot_empty_error(device_id, slot_id, "Selected slot has no data.")
    field_modes = field_modes_mapping_or_none(slot_entry.get("field_modes"))
    signature = slot_entry.get("signature") or compute_slot_signature(settings, field_modes)
    boot_state = boot_payload_from_value(entry.get("boot"))
    boot_flag, boot_slot, boot_signature = (
        boot_enabled(
            boot_state,
            logger=get_logger(LOGGER_NAME),
            operation="hardware.gpu_tuning.slot_apply.coerce_bool_flag",
        ),
        boot_state.get("slot"),
        boot_state.get("applied_signature"),
    )
    boot_change_requested = False
    if apply_flag is not None:
        boot_change_requested = bool(apply_flag) != boot_flag or (
            apply_flag and boot_slot != slot_id
        )
    unchanged = (
        boot_flag
        and boot_slot == slot_id
        and (boot_signature == signature)
        and (not boot_change_requested)
    )
    if (gpu_index := normalize_gpu_index(entry.get("gpu_index"))) is None:
        return gpu_index_error(device_id)
    return {
        "success": True,
        "slot_id": slot_id,
        "settings": copy.deepcopy(settings),
        "field_modes": copy.deepcopy(field_modes),
        "signature": signature,
        "gpu_index": gpu_index,
        "apply_flag": apply_flag,
        "unchanged": unchanged,
        "boot_state": copy.deepcopy(boot_state),
    }


def sync_finalize_slot_apply(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    device_id: str,
    slot_id: str,
    signature: str,
    apply_flag: bool | None,
    applied_at: str,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    logger.debug(
        "Finalizing GPU slot apply for device '%s', slot '%s'.",
        device_id,
        slot_id,
    )
    with storage.lock:
        payload = load_locked_payload(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            gpu_services=gpu_services,
            allow_create=False,
        )
        entry = devices(payload).get(device_id)
        if not isinstance(entry, dict):
            return {
                "success": True,
                "entry": None,
                "boot_changed": False,
                "warning": "Device removed before slot persistence update.",
            }
        original_boot = copy.deepcopy(entry.get("boot", {}))
        if apply_flag is not None:
            entry["boot"] = (
                pending_enabled_boot_payload(slot_id) if apply_flag else disabled_boot_payload()
            )
        boot_changed, entry_snapshot = record_slot_application_unlocked(
            storage,
            payload,
            device_id,
            slot_id,
            signature,
            applied_at,
        )
        if isinstance(entry_snapshot, dict):
            boot_changed = entry_snapshot.get("boot", {}) != original_boot
            storage.write_payload(payload)
            return {
                "success": True,
                "entry": copy.deepcopy(entry_snapshot),
                "boot_changed": boot_changed,
            }
        storage.write_payload(payload)
        return {
            "success": True,
            "entry": copy.deepcopy(entry),
            "boot_changed": boot_changed,
        }

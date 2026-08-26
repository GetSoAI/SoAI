"""SoAI - Startup GPU tuning profile application [backend/hardware/gpu_tuning/startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from core.validation.boolean_coercion import coerce_bool_flag
from hardware.control.profiles import (
    compute_slot_signature,
    default_boot_payload,
    normalize_slot_identifier,
)
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_errors import devices
from hardware.gpu_tuning.slot_payload import (
    load_locked_inventory_and_payload,
    load_locked_payload,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "sync_collect_startup_apply_targets",
    "sync_finalize_startup_apply",
    "sync_handle_dirty_startup",
)


def _load_startup_payload_unlocked(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    return load_locked_payload(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
        allow_create=True,
    )


def sync_handle_dirty_startup(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
) -> dict[str, JSONDict]:
    affected: dict[str, JSONDict] = {}
    with storage.lock:
        payload = _load_startup_payload_unlocked(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            gpu_services=gpu_services,
        )
        devices_payload, changed = (devices(payload), False)
        for device_id, entry in devices_payload.items():
            if not isinstance(entry, dict):
                continue
            if not isinstance((boot := entry.get("boot")), dict):
                entry["boot"], changed = (default_boot_payload(), True)
                affected[device_id] = copy.deepcopy(entry)
                continue
            if coerce_bool_flag(
                boot.get("enabled"),
                logger=logger,
                operation="hardware.gpu_tuning.startup.coerce_bool_flag",
                default=False,
                recover_message="Failed to parse boolean flag (non-critical).",
            ):
                boot["enabled"], changed = (False, True)
                affected[device_id] = copy.deepcopy(entry)
        if changed:
            storage.write_payload(payload)
    return affected


def sync_collect_startup_apply_targets(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    instructions: list[JSONDict] = []
    snapshots: dict[str, JSONDict] = {}
    disabled: list[str] = []
    with storage.lock:
        inventory, payload = load_locked_inventory_and_payload(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            gpu_services=gpu_services,
            allow_create=True,
        )
        devices_payload, changed_devices = (devices(payload), set[str]())
        for device_id, entry in devices_payload.items():
            if not isinstance(entry, dict):
                continue
            boot = entry.get("boot")
            if not isinstance(boot, dict) or (
                not coerce_bool_flag(
                    boot.get("enabled"),
                    logger=logger,
                    operation="hardware.gpu_tuning.startup.coerce_bool_flag",
                    default=False,
                    recover_message="Failed to parse boolean flag (non-critical).",
                )
            ):
                continue
            entry_dict = entry

            def disable_boot(
                *,
                entry_snapshot: JSONDict = entry_dict,
                device_identifier: str = device_id,
            ) -> None:
                entry_snapshot["boot"] = default_boot_payload()
                changed_devices.add(device_identifier)
                disabled.append(device_identifier)

            slot_raw = boot.get("slot")
            slot_id = (
                normalize_slot_identifier(slot_raw) if isinstance(slot_raw, str | int) else None
            )
            slots = entry_dict.get("slots")
            slot_entry = (
                slots.get(slot_id) if isinstance(slots, dict) and slot_id is not None else None
            )
            if not isinstance(slot_entry, dict):
                disable_boot()
                continue
            settings = slot_entry.get("settings")
            device_info = inventory.get(device_id)
            if (
                slot_id is None
                or (not isinstance(settings, dict))
                or not settings
                or (not isinstance(device_info, dict))
            ):
                disable_boot()
                continue
            if (gpu_index := normalize_gpu_index(device_info.get("gpu_index"))) is None:
                disable_boot()
                continue
            if not (
                isinstance((slot_signature := slot_entry.get("signature")), str) and slot_signature
            ):
                raw_field_modes = slot_entry.get("field_modes")
                slot_signature = compute_slot_signature(
                    settings,
                    raw_field_modes if isinstance(raw_field_modes, dict) else None,
                )
                slot_entry["signature"] = slot_signature
                changed_devices.add(device_id)
            raw_field_modes = slot_entry.get("field_modes")
            if entry_dict.get("gpu_index") != gpu_index:
                entry_dict["gpu_index"] = gpu_index
                changed_devices.add(device_id)
            instructions.append(
                {
                    "device_id": device_id,
                    "gpu_index": gpu_index,
                    "slot_id": slot_id,
                    "settings": copy.deepcopy(settings),
                    "field_modes": copy.deepcopy(
                        raw_field_modes if isinstance(raw_field_modes, dict) else {},
                    ),
                    "signature": slot_signature,
                    "last_applied_at": slot_entry.get("last_applied_at"),
                    "boot_state": copy.deepcopy(entry_dict.get("boot", {})),
                    "current_field_modes": copy.deepcopy(
                        (
                            entry_dict.get("field_modes")
                            if isinstance(entry_dict.get("field_modes"), dict)
                            else {}
                        ),
                    ),
                    "applied_settings": copy.deepcopy(
                        (
                            entry_dict.get("applied_settings")
                            if isinstance(entry_dict.get("applied_settings"), dict)
                            else {}
                        ),
                    ),
                },
            )
        if changed_devices:
            storage.write_payload(payload)
            devices_snapshot = devices(payload)
            for device_id in changed_devices:
                if isinstance((entry := devices_snapshot.get(device_id)), dict):
                    snapshots[device_id] = copy.deepcopy(entry)
    return {
        "instructions": instructions,
        "snapshots": snapshots,
        "disabled_devices": disabled,
    }


def sync_finalize_startup_apply(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    results: list[JSONDict],
    gpu_services: GpuServiceDependencies,
) -> dict[str, JSONDict]:
    if not results:
        return {}
    logger.debug("Finalizing %d GPU startup apply result(s).", len(results))
    updated: dict[str, JSONDict] = {}
    with storage.lock:
        payload = _load_startup_payload_unlocked(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            gpu_services=gpu_services,
        )
        devices_payload, changed_devices = (devices(payload), set[str]())
        for result in results:
            device_id, slot_id = (result.get("device_id"), result.get("slot_id"))
            entry = devices_payload.get(str(device_id)) if device_id else None
            slots_val = entry.get("slots") if isinstance(entry, dict) else None
            slots_dict = slots_val if isinstance(slots_val, dict) else {}
            slot_entry = slots_dict.get(str(slot_id)) if slot_id else None
            if not (
                isinstance(device_id, str)
                and isinstance(slot_id, str)
                and isinstance(entry, dict)
                and isinstance(slot_entry, dict)
            ):
                continue
            if isinstance((signature := result.get("signature")), str) and signature:
                slot_entry["signature"] = signature
            if applied_at := result.get("applied_at"):
                slot_entry["last_applied_at"] = applied_at
            boot_val = entry.get("boot", {})
            boot = boot_val if isinstance(boot_val, dict) else {}
            if boot.get("slot") == slot_id:
                if applied_at:
                    boot["applied_signature"], boot["applied_at"] = (
                        signature,
                        applied_at,
                    )
                elif result.get("boot_applied_at") and coerce_bool_flag(
                    boot.get("enabled"),
                    logger=logger,
                    operation="hardware.gpu_tuning.startup.coerce_bool_flag",
                    default=False,
                    recover_message="Failed to parse boolean flag (non-critical).",
                ):
                    boot["applied_signature"] = signature
                    if not boot.get("applied_at"):
                        boot["applied_at"] = result["boot_applied_at"]
                entry["boot"] = boot
            changed_devices.add(device_id)
        if changed_devices:
            storage.write_payload(payload)
            refreshed_devices = devices(payload)
            for device_id in changed_devices:
                if isinstance((entry := refreshed_devices.get(device_id)), dict):
                    updated[device_id] = copy.deepcopy(entry)
    return updated

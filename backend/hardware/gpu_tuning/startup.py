"""SoAI - Startup GPU tuning profile application [backend/hardware/gpu_tuning/startup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import (
    GPUControlCommitIntent,
    GPUControlPreflightRejection,
)
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_recovery_records import GPUStartupRecoveryRecord
from core.types.json import JSONDict
from core.types.json_value import require_json_dict
from core.validation.boolean_coercion import coerce_bool_flag
from core.validation.booleans import parse_bool_token_or_none
from hardware.control.profiles import (
    compute_slot_signature,
    default_boot_payload,
    normalize_slot_identifier,
)
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_inventory.physical_binding import resolve_gpu_physical_binding
from hardware.gpu_tuning.control_backend_selection import group_settings_by_control_backend
from hardware.gpu_tuning.control_saved_state_authority import control_state_digest
from hardware.gpu_tuning.control_worker_results import GPUControlOperationOutcome
from hardware.gpu_tuning.direct_prepared_apply import (
    GPUPreparedSettingsPlan,
    prepare_gpu_settings_plan,
    rejected_gpu_settings_outcome,
)
from hardware.gpu_tuning.effective_control_state import build_apply_settings_for_modes
from hardware.gpu_tuning.native_startup_reconciliation import derive_startup_record_promotion
from hardware.gpu_tuning.service_dependencies import GPUStartupAcquisitionResources
from hardware.gpu_tuning.setting_modes import normalize_field_modes_for_settings
from hardware.gpu_tuning.slot_capabilities import (
    get_tuning_capabilities_for_services,
    snapshot_tuning_inventory,
)
from hardware.gpu_tuning.startup_scope_acquisition import build_gpu_control_startup_scope
from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedGoal

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_control_types import GPUPreparedControl, GPUSlotReadResult
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies
    from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope


__all__ = (
    "require_fresh_startup_scope",
    "prepare_startup_legacy_slots",
    "GPUStartupBootPreparation",
    "prepare_startup_boot_slots",
)


def require_fresh_startup_scope(
    deps: GpuSettingsApplyDependencies,
    scope: GPUControlStartupScope,
    initial_read: GPUSlotReadResult,
    operation_id: str,
) -> None:
    fresh = build_gpu_control_startup_scope(
        executor=deps.executor,
        logger=deps.logger,
        gpu_services=deps.gpu_services,
        runtime_platform=deps.gpu_services.nvidia_nvml_gate.runtime_platform,
        intel_executable=deps.gpu_services.intel_executable,
        acquisition_id=f"{operation_id}:owned",
        policy=scope.policy,
        initial_records=scope.initial_records,
    )
    recorded = tuple((row.target, row.state, row.reason_code) for row in scope.recorded)
    fresh_recorded = tuple((row.target, row.state, row.reason_code) for row in fresh.recorded)
    if (
        scope.physical_snapshot.devices != fresh.physical_snapshot.devices
        or scope.physical_snapshot.vendors != fresh.physical_snapshot.vendors
        or recorded != fresh_recorded
    ):
        raise ValidationError("GPU startup physical scope changed before effects.")
    if scope.legacy_plan is not None:
        if fresh.legacy_plan is None:
            raise ValidationError("GPU startup native routes disappeared before effects.")
        routes = tuple(
            (row.vendor, row.backend, row.state, row.devices, row.reason_code)
            for row in scope.legacy_plan.rosters
        )
        fresh_routes = tuple(
            (row.vendor, row.backend, row.state, row.devices, row.reason_code)
            for row in fresh.legacy_plan.rosters
        )
        facilities = tuple(
            (row.target, row.facilities, row.rejection) for row in scope.legacy_plan.devices
        )
        fresh_facilities = tuple(
            (row.target, row.facilities, row.rejection) for row in fresh.legacy_plan.devices
        )
        if routes != fresh_routes or facilities != fresh_facilities:
            raise ValidationError("GPU startup native facility scope changed before effects.")
    with deps.storage.lock:
        if deps.storage.read_payload() != initial_read:
            raise ValidationError("GPU startup saved authority changed before effects.")


def prepare_startup_legacy_slots(
    deps: GpuSettingsApplyDependencies,
    scope: GPUControlStartupScope,
    operation_id: str,
    cancellation_token: CancellationTokenProtocol,
) -> dict[str, GPUPreparedControl]:
    prepared: dict[str, GPUPreparedControl] = {}
    if scope.legacy_plan is None:
        return prepared
    resources = GPUStartupAcquisitionResources(deps.executor, deps.logger, deps.gpu_services)
    for plan in scope.legacy_plan.devices:
        cancellation_token.raise_if_cancelled()
        if plan.record is None or plan.rejection is not None:
            continue
        originals = tuple(
            row
            for row in scope.recorded
            if row.target is not None
            and row.target.device_id == plan.target.device_id
            and row.goal == GPUStartupRecordedGoal.ORIGINAL
        )
        if originals:
            if len(originals) != 1:
                raise ValidationError("GPU startup promotion has ambiguous original scope.")
            proof = derive_startup_record_promotion(
                originals[0].record,
                plan.record,
                target=plan.target,
                executor=deps.executor,
                logger=deps.logger,
                gpu_services=deps.gpu_services,
                runtime_platform=deps.gpu_services.nvidia_nvml_gate.runtime_platform,
                acquisition_id=f"{operation_id}:promotion:{plan.target.device_id}",
                intel_executable=deps.gpu_services.intel_executable,
            )
            outer = GPUStartupRecoveryRecord(
                f"{operation_id}:slot:{plan.target.device_id}",
                plan.target.device_id,
                originals[0].record,
                plan.record,
                None,
            )
            with deps.storage.lock:
                receipt = deps.native_control_recovery.promote_startup(
                    plan.target,
                    record=outer,
                    expected_read=deps.storage.read_payload(),
                    proof=proof,
                    resources=resources,
                )
        else:
            receipt = deps.native_control_recovery.prepare_startup_legacy(
                plan.target,
                plan.record,
                startup_operation_id=f"{operation_id}:slot:{plan.target.device_id}",
            )
        prepared[plan.record.operation_id] = receipt
    return prepared


@dataclass(frozen=True, slots=True)
class GPUStartupBootPreparation:
    initial_read: GPUSlotReadResult
    candidate_payload: JSONDict
    plans: tuple[GPUPreparedSettingsPlan, ...]
    changed_devices: tuple[str, ...]


def prepare_startup_boot_slots(
    deps: GpuSettingsApplyDependencies,
    cancellation_token: CancellationTokenProtocol,
    *,
    operation_id: str,
) -> GPUStartupBootPreparation | GPUControlOperationOutcome:
    cancellation_token.raise_if_cancelled()
    with deps.storage.lock:
        initial = copy.deepcopy(deps.storage.read_payload())
    if initial.recovery_records:
        raise ValidationError("GPU clean startup cannot discard retained recovery.")
    payload = copy.deepcopy(initial.payload)
    devices = require_json_dict(payload.get("devices"), label="GPU startup devices")
    inventory_required = initial.migration_required
    for raw_entry in devices.values():
        entry = require_json_dict(raw_entry, label="GPU startup saved device")
        boot = entry.get("boot")
        if not isinstance(boot, dict) or parse_bool_token_or_none(boot.get("enabled")) is not False:
            inventory_required = True
    inventory = (
        snapshot_tuning_inventory(
            executor=deps.executor,
            detailed_gpu_info=deps.detailed_gpu_info,
            gpu_services=deps.gpu_services,
        )
        if inventory_required
        else {}
    )
    instructions: list[tuple[str, str, str, JSONDict, JSONDict]] = []
    changed: list[str] = []
    for device_id, raw_entry in devices.items():
        entry = require_json_dict(raw_entry, label="GPU startup saved device")
        devices[device_id] = entry
        boot = entry.get("boot")
        if not isinstance(boot, dict) or not coerce_bool_flag(
            boot.get("enabled"),
            logger=deps.logger,
            operation="hardware.gpu_tuning.startup.boot",
            default=False,
            recover_message="GPU boot preference is unavailable.",
        ):
            continue
        slot_value = boot.get("slot")
        slot_id = (
            normalize_slot_identifier(slot_value) if isinstance(slot_value, str | int) else None
        )
        slots = entry.get("slots")
        slot = slots.get(slot_id) if isinstance(slots, dict) and slot_id is not None else None
        settings = slot.get("settings") if isinstance(slot, dict) else None
        device_info = inventory.get(device_id)
        if (
            slot_id is None
            or not isinstance(slot, dict)
            or not isinstance(settings, dict)
            or not settings
            or not isinstance(device_info, dict)
        ):
            if device_id in inventory or (
                not initial.migration_required and entry.get("device_id") == device_id
            ):
                entry["boot"] = default_boot_payload()
                changed.append(device_id)
            continue
        index = normalize_gpu_index(device_info.get("gpu_index"))
        if index is None:
            raise ValidationError("GPU startup boot target lacks its actual public index.")
        modes_value = slot.get("field_modes")
        modes = normalize_field_modes_for_settings(
            settings, modes_value if isinstance(modes_value, dict) else None
        )
        signature = slot.get("signature")
        if not isinstance(signature, str) or not signature:
            signature = compute_slot_signature(settings, modes)
            slot["signature"] = signature
            changed.append(device_id)
        if entry.get("gpu_index") != index:
            entry["gpu_index"] = index
            changed.append(device_id)
        instructions.append((device_id, slot_id, signature, settings, modes))
    payload["devices"] = devices
    capabilities = (
        get_tuning_capabilities_for_services(
            executor=deps.executor, gpu_services=deps.gpu_services, logger=deps.logger
        )
        if instructions
        else {}
    )
    plans: list[GPUPreparedSettingsPlan] = []
    for device_id, slot_id, signature, settings, modes in instructions:
        cancellation_token.raise_if_cancelled()
        device_info = inventory[device_id]
        binding = resolve_gpu_physical_binding(device_info, list(inventory.values()))
        if binding.state != GPUPhysicalBindingState.BOUND or binding.device is None:
            raise ValidationError("GPU boot application lacks unique actual physical scope.")
        index = normalize_gpu_index(device_info.get("gpu_index"))
        if index is None:
            raise ValidationError("GPU startup target index changed during preparation.")
        caps = (
            get_capabilities_for_device(capabilities, device_id, index, selected_gpu=device_info)
            or {}
        )
        grouped = group_settings_by_control_backend(
            build_apply_settings_for_modes(settings, modes), caps
        )
        fields = tuple(field for bucket in grouped.values() for field in bucket)
        intent = GPUControlCommitIntent(
            fields, control_state_digest(payload, device_id), slot_id, signature, True
        )
        plan = prepare_gpu_settings_plan(
            deps,
            operation_id=f"{operation_id}:{device_id}",
            target=binding.device,
            gpu_index=index,
            capabilities=caps,
            settings=settings,
            field_modes=modes,
            commit_intent=intent,
            cancellation_token=cancellation_token,
        )
        if isinstance(plan, GPUControlPreflightRejection):
            return rejected_gpu_settings_outcome(device_id, plan)
        plans.append(plan)
    cancellation_token.raise_if_cancelled()
    with deps.storage.lock:
        if deps.storage.read_payload() != initial:
            raise ValidationError("GPU startup saved authority changed during preparation.")
    return GPUStartupBootPreparation(initial, payload, tuple(plans), tuple(dict.fromkeys(changed)))

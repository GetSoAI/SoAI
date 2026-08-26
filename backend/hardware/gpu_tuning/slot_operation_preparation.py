"""SoAI - GPU slot operation preparation [backend/hardware/gpu_tuning/slot_operation_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.types.json import JSONValue
from core.validation.booleans import parse_bool
from hardware.gpu_tuning.apply_at_boot_flag import parse_apply_at_boot_flag_or_error
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_errors import (
    SlotOperationContext,
    load_locked_slot_operation_context_for_device,
    resolve_slot_identifier_or_error,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "PreparedSlotApplyOperation",
    "PreparedSlotBootToggleOperation",
    "PreparedSlotOperation",
    "prepare_slot_apply_operation",
    "prepare_slot_boot_toggle_operation",
)


@dataclass(frozen=True, slots=True)
class PreparedSlotOperation:
    slot_id: str
    context: SlotOperationContext


@dataclass(frozen=True, slots=True)
class PreparedSlotApplyOperation:
    slot_id: str
    context: SlotOperationContext
    apply_flag: bool | None


@dataclass(frozen=True, slots=True)
class PreparedSlotBootToggleOperation:
    slot_id: str
    context: SlotOperationContext
    flag: bool


def _load_prepared_slot_operation_context(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    slot_id: str,
    gpu_services: GpuServiceDependencies,
) -> PreparedSlotOperation | JSONDict:
    context = load_locked_slot_operation_context_for_device(
        executor,
        storage,
        detailed_gpu_info,
        device_id,
        gpu_services,
    )
    if context.error:
        return context.error
    return PreparedSlotOperation(slot_id=slot_id, context=context)


def prepare_slot_apply_operation(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    slot: str | int,
    apply_at_boot: bool | None,
    gpu_services: GpuServiceDependencies,
) -> PreparedSlotApplyOperation | JSONDict:
    slot_id_or_error = resolve_slot_identifier_or_error(slot)
    if isinstance(slot_id_or_error, dict):
        return slot_id_or_error
    apply_flag, apply_error = parse_apply_at_boot_flag_or_error(
        device_id=device_id,
        slot_id=slot_id_or_error,
        apply_at_boot=apply_at_boot,
        default=False,
    )
    if apply_error is not None:
        return apply_error
    prepared = _load_prepared_slot_operation_context(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        device_id=device_id,
        slot_id=slot_id_or_error,
        gpu_services=gpu_services,
    )
    if isinstance(prepared, dict):
        return prepared
    return PreparedSlotApplyOperation(
        slot_id=prepared.slot_id,
        context=prepared.context,
        apply_flag=apply_flag,
    )


def prepare_slot_boot_toggle_operation(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    slot: str | int,
    enabled: JSONValue,
    gpu_services: GpuServiceDependencies,
) -> PreparedSlotBootToggleOperation | JSONDict:
    slot_id_or_error = resolve_slot_identifier_or_error(slot)
    if isinstance(slot_id_or_error, dict):
        return slot_id_or_error
    flag = parse_bool(enabled, default=None)
    if flag is None:
        return build_gpu_operation_error(
            "invalid_payload",
            "The 'enabled' flag must be a boolean value.",
            device_id=device_id,
            slot=slot_id_or_error,
        )
    prepared = _load_prepared_slot_operation_context(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        device_id=device_id,
        slot_id=slot_id_or_error,
        gpu_services=gpu_services,
    )
    if isinstance(prepared, dict):
        return prepared
    return PreparedSlotBootToggleOperation(
        slot_id=prepared.slot_id,
        context=prepared.context,
        flag=flag,
    )

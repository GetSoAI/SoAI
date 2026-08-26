"""SoAI - GPU tuning event emission helpers [backend/hardware/gpu_tuning/events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_system import GPUSavedSettingsChangedEvent
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.system.protocols import CommandExecutorProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.types.json import JSONDict
from core.validation.boolean_coercion import coerce_bool_flag
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.event_publish import (
    emit_active_slot_event,
    emit_boot_preference_event,
)
from hardware.gpu_tuning.result_flags import is_success_result
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_capabilities import get_tuning_capabilities_for_services
from hardware.gpu_tuning.slot_state import build_live_state
from hardware.operations import can_emit_events, schedule_event_bus_publish

__all__ = (
    "SlotStateEventDependencies",
    "emit_active_slot_event",
    "emit_boot_preference_event_for_entry",
    "emit_mutation_events",
    "emit_slot_and_boot_event",
    "emit_slot_and_boot_events",
    "emit_slot_and_boot_events_and_clear_active",
    "emit_slot_state_event",
)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.events"
OPERATION = "hardware_presets.emit_slot_state_event"


@dataclass(frozen=True, slots=True)
class SlotStateEventDependencies:
    executor: CommandExecutorProtocol
    event_bus: EventBusProtocol | None
    main_loop: asyncio.AbstractEventLoop | None
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    logger: TraceLogger
    gpu_services: GpuServiceDependencies

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SlotStateEventDependencies",
            cancellation_binder=self.cancellation_binder,
            executor=self.executor,
            finalizer_tracker=self.finalizer_tracker,
            gpu_services=self.gpu_services,
            logger=self.logger,
        )


def build_slot_state_event_dependencies_or_none(
    executor: CommandExecutorProtocol,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
) -> SlotStateEventDependencies | None:
    if not can_emit_events(event_bus, main_loop):
        return None
    return SlotStateEventDependencies(
        executor=executor,
        event_bus=event_bus,
        main_loop=main_loop,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
        gpu_services=gpu_services,
    )


def emit_slot_state_event(
    deps: SlotStateEventDependencies,
    *,
    device_id: str,
    entry: JSONDict,
) -> None:
    if not can_emit_events(deps.event_bus, deps.main_loop):
        return
    if deps.event_bus is None or deps.main_loop is None:
        return
    slots_value = entry.get("slots")
    boot_value = entry.get("boot")
    slots_payload = copy.deepcopy(slots_value) if isinstance(slots_value, dict) else {}
    boot_payload = copy.deepcopy(boot_value) if isinstance(boot_value, dict) else {}
    try:
        capabilities = get_tuning_capabilities_for_services(
            executor=deps.executor,
            gpu_services=deps.gpu_services,
            logger=deps.logger,
        )
        cap_entry = get_capabilities_for_device(
            capabilities,
            device_id,
            normalize_gpu_index(entry.get("gpu_index")),
        )
        live_payload = build_live_state(device_id, entry, cap_entry)
    except RECOVERABLE_EXCEPTIONS as error:
        log_exception(
            deps.logger,
            error,
            message="Failed to build live GPU slot state",
            operation=OPERATION,
            details={"device_id": device_id},
        )
        live_payload = {}
    event = GPUSavedSettingsChangedEvent(
        device_id=device_id,
        slots=slots_payload,
        boot=boot_payload,
        live=copy.deepcopy(live_payload),
    )
    schedule_event_bus_publish(
        deps.event_bus,
        deps.main_loop,
        event,
        label=f"gpu-slot-state-{device_id}",
        owner_prefix="hardware-presets",
        cancellation_binder=deps.cancellation_binder,
        finalizer_tracker=deps.finalizer_tracker,
        logger=deps.logger,
    )


def emit_cleared_active_slot_event(
    slot_state_deps: SlotStateEventDependencies | None,
    *,
    device_id: str,
) -> None:
    if slot_state_deps is None:
        return
    emit_active_slot_event(
        event_bus=slot_state_deps.event_bus,
        main_loop=slot_state_deps.main_loop,
        cancellation_binder=slot_state_deps.cancellation_binder,
        finalizer_tracker=slot_state_deps.finalizer_tracker,
        logger=slot_state_deps.logger,
        device_id=device_id,
        slot_id=None,
        signature=None,
        applied_at=None,
    )


def emit_boot_preference_event_for_entry(
    deps: SlotStateEventDependencies,
    *,
    device_id: str,
    entry: JSONDict,
) -> None:
    boot_payload_value = entry.get("boot")
    boot_payload = boot_payload_value if isinstance(boot_payload_value, dict) else {}
    emit_boot_preference_event(
        event_bus=deps.event_bus,
        main_loop=deps.main_loop,
        cancellation_binder=deps.cancellation_binder,
        finalizer_tracker=deps.finalizer_tracker,
        logger=deps.logger,
        device_id=device_id,
        boot_payload=boot_payload,
    )


def emit_slot_and_boot_event(
    slot_state_deps: SlotStateEventDependencies | None,
    *,
    device_id: str,
    entry: JSONDict,
) -> None:
    if slot_state_deps is None:
        return
    emit_slot_state_event(slot_state_deps, device_id=device_id, entry=entry)
    emit_boot_preference_event_for_entry(slot_state_deps, device_id=device_id, entry=entry)


def emit_slot_and_boot_events(
    slot_state_deps: SlotStateEventDependencies | None,
    *,
    entries_by_device_id: Mapping[str, JSONDict],
) -> None:
    if slot_state_deps is None:
        return
    for device_id, entry in entries_by_device_id.items():
        emit_slot_and_boot_event(slot_state_deps, device_id=device_id, entry=entry)


def emit_slot_and_boot_events_and_clear_active(
    slot_state_deps: SlotStateEventDependencies | None,
    *,
    entries_by_device_id: Mapping[str, JSONDict],
    cleared_device_ids: list[str] | tuple[str, ...],
) -> None:
    emit_slot_and_boot_events(slot_state_deps, entries_by_device_id=entries_by_device_id)
    for device_id in cleared_device_ids:
        emit_cleared_active_slot_event(slot_state_deps, device_id=device_id)


def emit_mutation_events(
    *,
    executor: CommandExecutorProtocol,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    result: JSONDict,
    emit_boot_on_success: bool,
    gpu_services: GpuServiceDependencies,
) -> None:
    entry_value = result.get("entry")
    if not (
        is_success_result(
            result,
            logger=get_logger(LOGGER_NAME),
            operation="hardware.gpu_tuning.events.is_success_result",
        )
        and isinstance(entry_value, dict)
        and can_emit_events(event_bus, main_loop)
    ):
        return
    entry = entry_value
    device_id = result.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        return
    slot_state_deps = build_slot_state_event_dependencies_or_none(
        executor=executor,
        event_bus=event_bus,
        main_loop=main_loop,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
        gpu_services=gpu_services,
    )
    if slot_state_deps is None:
        return
    emit_slot_state_event(
        slot_state_deps,
        device_id=device_id,
        entry=entry,
    )
    if (
        coerce_bool_flag(
            result.get("boot_changed"),
            logger=logger,
            operation="hardware.gpu_tuning.events.coerce_bool_flag",
            default=False,
            recover_message="Failed to parse boolean flag (non-critical).",
        )
        or emit_boot_on_success
    ):
        emit_boot_preference_event_for_entry(slot_state_deps, device_id=device_id, entry=entry)

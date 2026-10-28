"""SoAI - GPU tuning event publish helpers [backend/hardware/gpu_tuning/event_publish.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import copy
from collections.abc import Sequence

from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.events.types_system import (
    GPUActiveSlotChangedEvent,
    GPUBootPreferenceChangedEvent,
    GPUStartupWarningEvent,
)
from core.hardware.gpu_control_types import GPUControlCommitAcknowledgement
from core.logging.protocols import TraceLogger
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.types.json import JSONDict
from core.types.json_value import require_json_dict
from hardware.gpu_tuning.control_operation_finalization import GPUControlFinalizationTarget
from hardware.gpu_tuning.control_worker_results import GPUControlOperationOutcome
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.operations import can_emit_events, schedule_event_bus_publish

__all__ = (
    "emit_active_slot_event",
    "emit_boot_preference_event",
    "emit_gpu_startup_warning",
)


def emit_active_slot_event(
    *,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    device_id: str,
    slot_id: str | None,
    signature: str | None,
    applied_at: str | None,
) -> None:
    if not can_emit_events(event_bus, main_loop):
        return
    if event_bus is None or main_loop is None:
        return
    event = GPUActiveSlotChangedEvent(
        device_id=device_id,
        slot=slot_id,
        signature=signature,
        applied_at=applied_at,
    )
    schedule_event_bus_publish(
        event_bus,
        main_loop,
        event,
        label=f"gpu-active-slot-{device_id}",
        owner_prefix="hardware-presets",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )


def emit_boot_preference_event(
    *,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    device_id: str,
    boot_payload: JSONDict,
) -> None:
    if not can_emit_events(event_bus, main_loop):
        return
    if event_bus is None or main_loop is None:
        return
    event = GPUBootPreferenceChangedEvent(device_id=device_id, boot=copy.deepcopy(boot_payload))
    schedule_event_bus_publish(
        event_bus,
        main_loop,
        event,
        label=f"gpu-boot-pref-{device_id}",
        owner_prefix="hardware-presets",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )


def emit_gpu_startup_warning(
    *,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    device_ids: Sequence[str],
) -> None:
    if not can_emit_events(event_bus, main_loop):
        return
    if event_bus is None or main_loop is None:
        return
    message = "GPU boot preferences were disabled after an unsafe shutdown. Reapply slot settings to restore automatic startup."
    event = GPUStartupWarningEvent(device_ids=list(device_ids), message=message)
    schedule_event_bus_publish(
        event_bus,
        main_loop,
        event,
        label="gpu-startup-warning",
        owner_prefix="hardware-presets",
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )


def publish_verified_gpu_control_state(
    *,
    targets: tuple[GPUControlFinalizationTarget, ...],
    outcome: GPUControlOperationOutcome,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
) -> None:
    if not isinstance(outcome.committed, tuple):
        raise ValidationError("GPU commit acknowledgements require an immutable complete tuple.")
    frozen = {target.target.device_id: target for target in targets}
    if len(frozen) != len(targets):
        raise ValidationError("GPU committed event targets must have unique physical devices.")
    validated: list[GPUControlCommitAcknowledgement] = []
    for acknowledgement in outcome.committed:
        if not isinstance(acknowledgement, GPUControlCommitAcknowledgement):
            raise ValidationError("GPU event requires an actual typed commit acknowledgement.")
        prepared = acknowledgement.prepared
        target = frozen.pop(prepared.target.device_id, None)
        if (
            target is None
            or target.target != prepared.target
            or target.scope_digest != prepared.scope_digest
            or target.commit_intent != acknowledgement.commit_intent
        ):
            raise ValidationError("GPU committed event does not match its unique frozen authority.")
        results = tuple(
            result
            for result in outcome.native_results
            if result.operation_id == prepared.operation_id
            and result.target.device_id == prepared.target.device_id
        )
        if (
            len(results) != 1
            or not reduce_gpu_control_result(results[0], prepared=prepared).persistence_eligible
        ):
            raise ValidationError("GPU committed event lacks complete verified native evidence.")
        validated.append(acknowledgement)
    snapshots = require_json_dict(
        outcome.payload.get("committed_state_snapshots", {}), label="GPU committed state snapshots"
    )
    if snapshots and set(snapshots) != {ack.prepared.target.device_id for ack in validated}:
        raise ValidationError("GPU committed snapshots changed their exact acknowledged devices.")
    boots: dict[str, JSONDict] = {}
    for acknowledgement in validated:
        device_id = acknowledgement.prepared.target.device_id
        if device_id in snapshots:
            entry = require_json_dict(snapshots[device_id], label="GPU committed device state")
            if entry.get("device_id") is not None and entry["device_id"] != device_id:
                raise ValidationError(
                    "GPU committed snapshot conflicts with its acknowledged device."
                )
            boot = require_json_dict(entry.get("boot", {}), label="GPU committed boot state")
            intent = acknowledgement.commit_intent
            if intent.slot_id is not None:
                slots = require_json_dict(entry.get("slots"), label="GPU committed slots")
                slot = require_json_dict(slots.get(intent.slot_id), label="GPU committed slot")
                if (
                    slot.get("signature") != intent.slot_signature
                    or slot.get("last_applied_at") != acknowledgement.committed_at
                ):
                    raise ValidationError(
                        "GPU committed slot snapshots changed acknowledged authority."
                    )
            boots[device_id] = boot
    for acknowledgement in validated:
        intent = acknowledgement.commit_intent
        device_id = acknowledgement.prepared.target.device_id
        if device_id in boots:
            emit_boot_preference_event(
                event_bus=event_bus,
                main_loop=main_loop,
                cancellation_binder=cancellation_binder,
                finalizer_tracker=finalizer_tracker,
                logger=logger,
                device_id=device_id,
                boot_payload=boots[device_id],
            )
        emit_active_slot_event(
            event_bus=event_bus,
            main_loop=main_loop,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            logger=logger,
            device_id=acknowledgement.prepared.target.device_id,
            slot_id=intent.slot_id,
            signature=intent.slot_signature,
            applied_at=acknowledgement.committed_at,
        )

"""SoAI - Completed GPU operation event authority and publication [backend/hardware/gpu_tuning/control_operation_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.hardware.gpu_control_types import GPUControlCommitAcknowledgement
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskFinalizerTrackerProtocol
from core.types.json import JSONDict
from core.types.json_value import require_json_dict
from hardware.gpu_tuning.control_operation_finalization import (
    GPUControlFinalizationTarget,
    GPUControlSnapshotScope,
)
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.control_worker_results import (
    GPUControlOperationCompletion,
    GPUControlOperationOutcome,
)
from hardware.gpu_tuning.event_publish import (
    emit_gpu_startup_warning,
    publish_verified_gpu_control_state,
)
from hardware.gpu_tuning.events import (
    SlotStateEventDependencies,
    build_slot_state_event_dependencies_or_none,
    emit_mutation_events,
    emit_slot_and_boot_events_and_clear_active,
)
from hardware.gpu_tuning.mutation_leases import GPUControlMetadataScope
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope, GPUStartupRecordedGoal

__all__ = (
    "startup_control_event_targets",
    "snapshot_control_event_targets",
    "publish_completed_gpu_control_operation",
)


def startup_control_event_targets(
    scope: GPUControlStartupScope,
) -> tuple[GPUControlFinalizationTarget, ...]:
    targets = [
        (row.target, row.record)
        for row in scope.recorded
        if row.goal
        in (
            GPUStartupRecordedGoal.UNCOMMITTED_LEGACY,
            GPUStartupRecordedGoal.COMMITTED_LEGACY_TARGET,
        )
        and row.target is not None
    ]
    if scope.legacy_plan is not None:
        targets.extend(
            (row.target, row.record) for row in scope.legacy_plan.devices if row.record is not None
        )
    return tuple(
        GPUControlFinalizationTarget(
            target, record.commit_intent, target.device_id, recovery_scope_digest(record)
        )
        for target, record in targets
        if record.commit_intent is not None
    )


def snapshot_control_event_targets(
    scope: GPUControlSnapshotScope, outcome: GPUControlOperationOutcome
) -> tuple[GPUControlFinalizationTarget, ...]:
    for acknowledgement in outcome.committed:
        if not isinstance(acknowledgement, GPUControlCommitAcknowledgement):
            raise ValidationError("GPU snapshot event requires a typed commit acknowledgement.")
        scope.require_target(acknowledgement.prepared.target)
    return tuple(
        GPUControlFinalizationTarget(
            acknowledgement.prepared.target,
            acknowledgement.commit_intent,
            scope.result_key,
            acknowledgement.prepared.scope_digest,
        )
        for acknowledgement in outcome.committed
    )


def publish_completed_gpu_control_operation(
    *,
    targets: (
        tuple[GPUControlFinalizationTarget, ...]
        | GPUControlStartupScope
        | GPUControlMetadataScope
        | GPUControlSnapshotScope
    ),
    outcome: GPUControlOperationOutcome,
    completion: GPUControlOperationCompletion,
    payload: JSONDict,
    event_bus: EventBusProtocol | None,
    main_loop: asyncio.AbstractEventLoop | None,
    executor: CommandExecutorProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
) -> None:
    publish_verified_gpu_control_state(
        targets=(
            startup_control_event_targets(targets)
            if isinstance(targets, GPUControlStartupScope)
            else (
                snapshot_control_event_targets(targets, outcome)
                if isinstance(targets, GPUControlSnapshotScope)
                else (() if isinstance(targets, GPUControlMetadataScope) else targets)
            )
        ),
        outcome=outcome,
        event_bus=event_bus,
        main_loop=main_loop,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
    )
    if isinstance(targets, GPUControlMetadataScope):
        outcome.require_metadata_only()
    event_dependencies = SlotStateEventDependencies(
        executor=executor,
        event_bus=event_bus,
        main_loop=main_loop,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        logger=logger,
        gpu_services=gpu_services,
    )
    if "committed_state_snapshots" in payload or (
        isinstance(targets, GPUControlMetadataScope)
        and completion.failure is None
        and not outcome.cancelled
    ):
        emit_mutation_events(
            event_dependencies,
            result=payload,
            emit_boot_on_success=False,
        )
    if isinstance(targets, GPUControlStartupScope) and "startup_boot_snapshots" in outcome.payload:
        snapshots = require_json_dict(
            outcome.payload["startup_boot_snapshots"], label="GPU startup boot snapshots"
        )
        entries = {
            device_id: require_json_dict(value, label="GPU startup boot device")
            for device_id, value in snapshots.items()
        }
        slot_events = build_slot_state_event_dependencies_or_none(event_dependencies)
        emit_slot_and_boot_events_and_clear_active(
            slot_events, entries_by_device_id=entries, cleared_device_ids=tuple(entries)
        )
        emit_gpu_startup_warning(
            event_bus=event_bus,
            main_loop=main_loop,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            logger=logger,
            device_ids=tuple(entries),
        )

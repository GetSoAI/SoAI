"""SoAI - Recorded original GPU actuator footprint acquisition and facility scope projection [backend/hardware/gpu_tuning/startup_recorded_facilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import (
    GPUOriginalObservationState,
    GPURecoveryRecord,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_backend_observations import acquire_native_actuator_footprint
from hardware.gpu_tuning.native_backend_resources import native_backend_resources
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.startup_scope_types import GPUStartupFacilityScope

OPERATION_HARDWARE_GPU_STARTUP_LEGACY_PLANNING_RECORDED = (
    "hardware.gpu.startup_legacy_planning.recorded"
)

__all__ = ("acquire_recorded_startup_facilities",)


def acquire_recorded_startup_facilities(
    target: GPUPhysicalDevice,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ],
) -> tuple[GPUStartupFacilityScope, ...]:
    facilities: list[GPUStartupFacilityScope] = []
    for outer in initial_records:
        if outer.device_id != target.device_id:
            continue
        records: tuple[GPURecoveryRecord, ...]
        if isinstance(outer, GPUStartupRecoveryRecord):
            records = outer.original_record, outer.legacy_record
        elif isinstance(outer, GPUStartupLegacyRecoveryRecord):
            records = (outer.legacy_record,)
        else:
            records = (outer,)
        for record in records:
            pairs = tuple(
                dict.fromkeys((member.backend, member.field) for member in record.members)
            )
            state = GPUOriginalObservationState.OBSERVED
            reason: str | None = None
            try:
                with native_backend_resources(
                    executor=executor,
                    logger=logger,
                    gpu_services=gpu_services,
                    backends=tuple(
                        dict.fromkeys(backend for backend, _ in pairs if backend is not None)
                    ),
                    conversion_fields=(),
                    goal="original",
                ) as boundary:
                    for member in record.members:
                        acquire_native_actuator_footprint(boundary, record, target, member)
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                state = GPUOriginalObservationState.UNAVAILABLE
                reason = "recorded_native_footprint_unavailable"
                log_exception(
                    logger,
                    exception,
                    message="GPU startup recorded facility acquisition failed (non-critical).",
                    operation=OPERATION_HARDWARE_GPU_STARTUP_LEGACY_PLANNING_RECORDED,
                    details={"operation_id": record.operation_id, "device_id": target.device_id},
                    level="trace",
                )
            for backend, field in pairs:
                if backend is None:
                    state = GPUOriginalObservationState.UNAVAILABLE
                    reason = "recorded_native_backend_unavailable"
                facilities.append(
                    GPUStartupFacilityScope(
                        target,
                        backend or target.vendor,
                        field,
                        (
                            tuple(
                                recovery_member_key(member)
                                for member in record.members
                                if member.backend == backend and member.field == field
                            )
                            if backend is not None
                            else ()
                        ),
                        state,
                        reason,
                    )
                )
    return tuple(facilities)

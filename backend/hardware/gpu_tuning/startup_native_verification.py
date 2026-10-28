"""SoAI - Complete fresh native startup goal and facility verification [backend/hardware/gpu_tuning/startup_native_verification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalBindingState
from core.hardware.gpu_recovery_records import GPUOriginalObservationState
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.native_backend_observations import read_startup_record_goal
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.startup_route_applicability import require_applicable_startup_routes
from hardware.gpu_tuning.startup_scope_accounting import (
    require_complete_startup_accounting,
    same_startup_physical_device,
)
from hardware.gpu_tuning.startup_scope_acquisition import build_gpu_control_startup_scope
from hardware.gpu_tuning.startup_scope_types import (
    GPUControlStartupScope,
    GPUControlStartupVerification,
    GPULegacyResetRoster,
    GPUStartupFacilityScope,
    GPUStartupRecordedGoal,
    GPUStartupScopePolicy,
    GPUStartupScopeReadback,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies


__all__ = ("verify_gpu_control_startup_scope",)


def verify_gpu_control_startup_scope(
    scope: GPUControlStartupScope,
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
    acquisition_id: str,
    recorded_readbacks: tuple[GPUStartupScopeReadback, ...],
    legacy_readbacks: tuple[GPUStartupScopeReadback, ...],
) -> GPUControlStartupVerification:
    scope, recorded_readbacks, legacy_readbacks = copy.deepcopy(
        (scope, recorded_readbacks, legacy_readbacks)
    )
    require_complete_startup_accounting(scope)
    fresh = build_gpu_control_startup_scope(
        executor=executor,
        logger=logger,
        gpu_services=gpu_services,
        runtime_platform=gpu_services.nvidia_nvml_gate.runtime_platform,
        acquisition_id=acquisition_id,
        intel_executable=gpu_services.intel_executable,
        policy=scope.policy,
        initial_records=scope.initial_records,
    )
    require_complete_startup_accounting(fresh)
    if scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL and (
        not fresh.physical_snapshot.vendors
        or any(
            row.state != GPUInventoryReadState.OBSERVED for row in fresh.physical_snapshot.vendors
        )
    ):
        raise ValidationError("GPU startup final physical coverage is unavailable.")
    expected = {(row.record.operation_id, row.goal): row.record for row in scope.recorded}
    if any(row.state != GPUPhysicalBindingState.BOUND for row in fresh.recorded):
        raise ValidationError("GPU startup final recorded physical scope is unavailable.")
    facilities: tuple[GPUStartupFacilityScope, ...] = ()
    rosters: tuple[GPULegacyResetRoster, ...] = ()
    if scope.legacy_plan is not None:
        plan = fresh.legacy_plan
        if plan is None or {(row.vendor, row.backend) for row in plan.rosters} != {
            (row.vendor, row.backend) for row in scope.legacy_plan.rosters
        }:
            raise ValidationError("GPU startup final native routing omits or invents a route.")
        if len(scope.legacy_plan.devices) != len(plan.devices) or any(
            sum(
                same_startup_physical_device(initial.target, current.target)
                for current in plan.devices
            )
            != 1
            for initial in scope.legacy_plan.devices
        ):
            raise ValidationError("GPU startup final physical/native peer union changed.")
        for initial_roster in scope.legacy_plan.rosters:
            current_roster = next(
                row
                for row in plan.rosters
                if (row.vendor, row.backend) == (initial_roster.vendor, initial_roster.backend)
            )
            if len(initial_roster.devices) != len(current_roster.devices) or any(
                sum(
                    same_startup_physical_device(initial, current)
                    for current in current_roster.devices
                )
                != 1
                for initial in initial_roster.devices
            ):
                raise ValidationError("GPU startup final native roster membership changed.")
        initial_facilities = tuple(
            facility for device in scope.legacy_plan.devices for facility in device.facilities
        )
        current_facilities = tuple(
            facility for device in plan.devices for facility in device.facilities
        )
        facilities = _require_facility_scope(
            initial_facilities, current_facilities, recorded_readbacks + legacy_readbacks
        )
        rosters = plan.rosters
        require_applicable_startup_routes(
            rosters,
            plan=plan,
            initial_records=scope.initial_records,
            message="GPU startup final native coverage is unavailable.",
        )
        if any(device.rejection is not None for device in plan.devices) or any(
            facility.state == GPUOriginalObservationState.UNAVAILABLE for facility in facilities
        ):
            raise ValidationError("GPU startup final native automatic policy is unavailable.")
        for device in scope.legacy_plan.devices:
            if device.record is not None:
                expected[
                    (device.record.operation_id, GPUStartupRecordedGoal.UNCOMMITTED_LEGACY)
                ] = device.record
    rows = recorded_readbacks + legacy_readbacks
    if len(rows) != len(expected) or len(
        {(row.record.operation_id, row.goal) for row in rows}
    ) != len(rows):
        raise ValidationError("GPU startup final verification omits or duplicates an actual goal.")
    for row in rows:
        frozen = expected.get((row.record.operation_id, row.goal))
        if frozen is None or recovery_scope_digest(row.record) != recovery_scope_digest(frozen):
            raise ValidationError(
                "GPU startup final verification changed its immutable native goal."
            )
        reduce_gpu_control_result(row.result, prepared=row.prepared)
        actual = read_startup_record_goal(
            row.record,
            row.prepared,
            row.goal,
            executor=executor,
            logger=logger,
            gpu_services=gpu_services,
        )
        if (
            actual.failure_codes
            or row.result.failure_codes
            or tuple((member.observed_value, member.observed_mode) for member in actual.members)
            != tuple((member.observed_value, member.observed_mode) for member in row.result.members)
        ):
            raise ValidationError("GPU startup final native goal is unresolved or changed.")
    return GPUControlStartupVerification(
        scope,
        fresh.physical_snapshot,
        rosters,
        recorded_readbacks,
        legacy_readbacks,
        facilities,
    )


def _require_facility_scope(
    initial: tuple[GPUStartupFacilityScope, ...],
    current: tuple[GPUStartupFacilityScope, ...],
    readbacks: tuple[GPUStartupScopeReadback, ...],
) -> tuple[GPUStartupFacilityScope, ...]:
    matched: list[GPUStartupFacilityScope] = []
    for actual in current:
        candidates = tuple(
            facility
            for facility in initial
            if same_startup_physical_device(facility.target, actual.target)
            and (facility.backend, facility.field, facility.member_keys, facility.state)
            == (actual.backend, actual.field, actual.member_keys, actual.state)
        )
        if len(candidates) != 1 or candidates[0] in matched:
            raise ValidationError("GPU startup final native facility obligations changed.")
        matched.append(candidates[0])
    missing = tuple(facility for facility in initial if facility not in matched)
    for facility in missing:
        if (
            facility.state != GPUOriginalObservationState.OBSERVED
            or facility.field not in ("persistence_mode", "fan_control_policy", "performance_mode")
            or not facility.member_keys
        ):
            raise ValidationError("GPU startup final native facility obligations changed.")
        frozen_rows = tuple(
            row
            for row in readbacks
            if same_startup_physical_device(facility.target, row.prepared.target)
            and tuple(
                recovery_member_key(member)
                for member in row.record.members
                if member.backend == facility.backend and member.field == facility.field
            )
            == facility.member_keys
        )
        if len(frozen_rows) != 1:
            raise ValidationError("GPU startup omitted setup lacks its complete frozen goal proof.")
    return initial

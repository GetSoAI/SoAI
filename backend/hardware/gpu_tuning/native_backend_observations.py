"""SoAI - Fresh configured native readback and complete actuator footprints [backend/hardware/gpu_tuning/native_backend_observations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import ctypes
from dataclasses import replace
from typing import Literal

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_types import (
    GPUControlMemberResult,
    GPUControlResult,
    GPUPreparedControl,
    NativeMemberObservation,
)
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.logging.protocols import TraceLogger
from core.system.protocols import CommandExecutorProtocol
from hardware.gpu_tuning.control_recovery_records import recovery_member_key, require_record_target
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.native_backend_execution import NativeBackendExecution
from hardware.gpu_tuning.native_backend_resources import native_backend_resources
from hardware.gpu_tuning.native_control_results import build_native_member_result
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.startup_scope_types import (
    GPUStartupActuatorFootprint,
    GPUStartupRecordedGoal,
)
from hardware.vendors.amd.adl_capabilities import bind_adl_controls
from hardware.vendors.amd.adl_settings import observe_adl_clock_member
from hardware.vendors.amd.control_member_observations import read_amd_member_state
from hardware.vendors.intel.i915_frequency import read_i915_frequency_pair
from hardware.vendors.intel.native_control_observations import read_intel_frequency_pair
from hardware.vendors.nvidia.nvapi_control_observations import (
    nvapi_member_goal_matches,
    prepare_nvapi_member_invocation,
)
from hardware.vendors.nvidia.nvml_member_execution import (
    nvml_goal_matches,
    read_nvml_control_member,
)
from hardware.vendors.nvidia.nvml_physical_binding import acquire_nvml_physical_binding
from hardware.vendors.nvidia.settings_control_observations import read_settings_member_state

OPERATION_HARDWARE_GPU_STARTUP_NATIVE_READBACK = "hardware.gpu.startup_native_readback"


__all__ = (
    "observe_native_backend_member",
    "acquire_native_actuator_footprint",
    "read_startup_record_goal",
)


def observe_native_backend_member(
    boundary: NativeBackendExecution,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> NativeMemberObservation:
    _require_observation_scope(record, prepared, member, goal)
    return _read_native_member(boundary, record, prepared.target, member, goal)


def _read_native_member(
    boundary: NativeBackendExecution,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
    goal: Literal["requested", "original"],
) -> NativeMemberObservation:
    if member.backend == "nvml":
        module = boundary.nvml_module
        if module is None:
            raise StateError("NVML configured readback module is unavailable.")
        native_failures: tuple[type[Exception], ...] = (
            module.NVMLError,
            ctypes.ArgumentError,
            *HANDLED_RUNTIME_EXCEPTIONS,
        )
        try:
            bound = acquire_nvml_physical_binding(module, target=target)
            observed = read_nvml_control_member(
                module, bound.handle, member, record, boundary.resolver, goal
            )
        except native_failures as exception:
            raise StateError(
                "NVML configured native readback failed.", cause=exception
            ) from exception
        return NativeMemberObservation(
            observed.value, observed.mode, nvml_goal_matches(member, observed, goal)
        )
    if member.backend == "nvapi":
        if boundary.query_interface is None:
            raise StateError("NvAPI configured readback acquisition is unavailable.")
        _, observed_nvapi, _ = prepare_nvapi_member_invocation(
            boundary.executor,
            record,
            target,
            member,
            executable=boundary.gpu_services.nvidia_smi_executable,
            query_interface=boundary.query_interface,
            nvml_module=boundary.nvml_module,
            goal=goal,
            purpose="observe",
        )
        return NativeMemberObservation(
            observed_nvapi.value,
            observed_nvapi.mode,
            nvapi_member_goal_matches(member, observed_nvapi, goal),
        )
    if member.backend == "nvidia_settings":
        if boundary.settings_session is None:
            raise StateError("NVIDIA settings configured readback session is unavailable.")
        return read_settings_member_state(
            boundary.settings_session, record, target, member, goal=goal, stage=False
        ).observation
    if member.backend == "amd_adl":
        if boundary.adl_session is None:
            raise StateError("ADL configured readback session is unavailable.")
        return observe_adl_clock_member(
            bind_adl_controls(boundary.adl_session, boundary.executor, target), member, goal=goal
        )[0]
    if member.backend in ("amd_smi", "amd_overdrive"):
        return read_amd_member_state(
            boundary.executor, record, target, member, goal=goal, stage=False
        ).observation
    if member.backend in ("intel_xpum", "intel_i915"):
        if member.backend == "intel_i915":
            _, members, observations = read_i915_frequency_pair(record, target, member, goal=goal)
        else:
            _, members, observations, _ = read_intel_frequency_pair(
                boundary.executor,
                boundary.gpu_services.intel_executable,
                record,
                target,
                member,
                goal=goal,
            )
        selected = tuple(
            observed
            for item, observed in zip(members, observations, strict=True)
            if recovery_member_key(item) == recovery_member_key(member)
        )
        if len(selected) != 1:
            raise StateError("Intel configured readback omits its selected endpoint.")
        return selected[0]
    raise StateError("The native member has no proved configured observation owner.")


def acquire_native_actuator_footprint(
    boundary: NativeBackendExecution,
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    member: GPURecoveryMember,
) -> GPUStartupActuatorFootprint:
    require_record_target(record, target)
    if member not in record.members:
        raise ValidationError("Native footprint omits its selected immutable member.")
    affected: tuple[GPURecoveryMember, ...] = (member,)
    if member.backend == "intel_i915":
        _, affected, _ = read_i915_frequency_pair(record, target, member, goal="original")
        actuator = "rps_max_freq_mhz"
    elif member.backend == "intel_xpum":
        _, affected, _, _ = read_intel_frequency_pair(
            boundary.executor,
            boundary.gpu_services.intel_executable,
            record,
            target,
            member,
            goal="original",
        )
        actuator = "frequencyrange"
    else:
        _read_native_member(boundary, record, target, member, "original")
        actuator = member.member_id
        if member.backend == "nvml" and member.member_id == "application_clocks":
            affected = tuple(
                item
                for item in record.members
                if item.backend == "nvml" and item.member_id == "application_clocks"
            )
            if len(affected) != 2:
                raise ValidationError("NVML application actuator requires its complete pair.")
            for item in affected:
                _read_native_member(boundary, record, target, item, "original")
            actuator = "nvmlDeviceSetApplicationsClocks"
        elif member.backend == "nvapi" and member.field == "fan_speed":
            affected = tuple(
                item
                for item in record.members
                if item.backend == "nvapi" and item.field == "fan_speed"
            )
            actuator = "NvAPI_GPU_ClientFanCoolersSetControl"
        elif member.backend == "nvidia_settings" and member.member_id == "gpu_fan_policy":
            affected = tuple(
                item
                for item in record.members
                if item.backend == "nvidia_settings"
                and (item.member_id == "gpu_fan_policy" or item.field == "fan_speed")
            )
            if len(affected) < 2:
                raise StateError(
                    "NVIDIA settings shared fan policy has unproved physical coverage."
                )
            for item in affected:
                _read_native_member(boundary, record, target, item, "original")
            actuator = "GPUFanControlState"
        elif member.backend == "amd_overdrive" and member.field in ("core_clock", "mem_clock"):
            affected = tuple(
                item
                for item in record.members
                if item.backend == "amd_overdrive" and item.field in ("core_clock", "mem_clock")
            )
            actuator = "pp_od_clk_voltage:commit"
        elif member.backend == "amd_overdrive" and member.field == "performance_mode":
            raise StateError(
                "AMD performance policy has no independently isolated setter footprint."
            )
    if member.backend is None:
        raise ValidationError("Native footprint requires its exact backend.")
    return GPUStartupActuatorFootprint(
        target,
        member.backend,
        actuator,
        tuple(recovery_member_key(item) for item in affected),
        tuple(dict.fromkeys(item.field for item in affected)),
        tuple(
            recovery_member_key(item)
            for item in affected
            if item.field in ("persistence_mode", "fan_control_policy", "performance_mode")
        ),
    )


def _require_observation_scope(
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    member: GPURecoveryMember,
    goal: Literal["requested", "original"],
) -> None:
    require_record_target(record, prepared.target)
    if (
        goal not in ("requested", "original")
        or record.operation_id != prepared.operation_id
        or recovery_scope_digest(record) != prepared.scope_digest
        or member not in record.members
        or set(prepared.member_keys) != {recovery_member_key(item) for item in record.members}
    ):
        raise ValidationError("Native observation changed its immutable record or receipt scope.")


def read_startup_record_goal(
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    goal: GPUStartupRecordedGoal,
    *,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    gpu_services: GpuServiceDependencies,
) -> GPUControlResult:
    if not isinstance(goal, GPUStartupRecordedGoal):
        raise ValidationError("GPU startup readback requires its actual recorded goal.")
    record = copy.deepcopy(record)
    native_goal: Literal["requested", "original"] = (
        "original" if goal == GPUStartupRecordedGoal.ORIGINAL else "requested"
    )
    for member in record.members:
        _require_observation_scope(record, prepared, member, native_goal)
    observations: tuple[NativeMemberObservation, ...] = ()
    failure: str | None = None
    backends = tuple(dict.fromkeys(member.backend for member in record.members if member.backend))
    conversion_fields = tuple(
        member.field
        for member in record.members
        if native_goal == "requested"
        and member.backend == "nvapi"
        and record.requested_modes[member.field] == "manual"
        and member.field in ("power_limit", "core_clock", "mem_clock")
    )
    try:
        with native_backend_resources(
            executor=executor,
            logger=logger,
            gpu_services=gpu_services,
            backends=backends,
            conversion_fields=conversion_fields,
            goal=native_goal,
        ) as boundary:
            observations = tuple(
                observe_native_backend_member(boundary, record, prepared, member, goal=native_goal)
                for member in record.members
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="GPU startup configured goal readback failed (non-critical).",
            operation=OPERATION_HARDWARE_GPU_STARTUP_NATIVE_READBACK,
            details={"operation_id": record.operation_id, "device_id": record.device_id},
            level="trace",
        )
        failure = "native_query_failed"
    if failure is None and not all(observed.target_matched for observed in observations):
        failure = "native_readback_mismatched"
    results: list[GPUControlMemberResult] = []
    for index, member in enumerate(record.members):
        observed = observations[index] if observations else None
        outcome = build_native_member_result(member, observed, False, failure, native_goal)
        if native_goal == "requested":
            outcome = replace(
                outcome,
                recovery_member=replace(
                    outcome.recovery_member, changed=member.changed, effect=member.effect
                ),
            )
        results.append(outcome)
    return GPUControlResult(
        operation_id=record.operation_id,
        target=prepared.target,
        members=tuple(results),
        requested_fields=tuple(record.requested_settings),
        messages=(),
        failure_codes=() if failure is None else (failure,),
    )

"""SoAI - Fresh NVML member proof and native invocation evidence [backend/hardware/vendors/nvidia/nvml_member_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING, Literal

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    GPUPreparedControl,
    NativeMemberObservation,
)
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.protocols import GPUControlRecoveryProtocol
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import build_native_member_result
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
    NvmlControlObservation,
    NvmlNativeFunctionResolverProtocol,
)
from hardware.vendors.nvidia.nvml_actuator_acquisition import (
    invoke_nvml_member_actuator,
    require_nvml_member_actuators,
)
from hardware.vendors.nvidia.nvml_application_clock_execution import invoke_nvml_application_pair
from hardware.vendors.nvidia.nvml_application_clock_preparation import (
    application_clock_members,
    read_nvml_application_observations,
)
from hardware.vendors.nvidia.nvml_clock_observations import (
    read_nvml_clock_member,
    read_nvml_original_clock_member,
)
from hardware.vendors.nvidia.nvml_clock_offset_abi import NvmlClockOffsetError
from hardware.vendors.nvidia.nvml_physical_binding import acquire_nvml_physical_binding
from hardware.vendors.nvidia.tuning_nvml import (
    read_nvml_original_persistence_member,
    read_nvml_persistence_member,
)
from hardware.vendors.nvidia.tuning_nvml_controls import (
    read_nvml_fan_member,
    read_nvml_original_fan_member,
)
from hardware.vendors.nvidia.tuning_power_limit import (
    read_nvml_original_power_member,
    read_nvml_power_member,
)

if TYPE_CHECKING:
    from hardware.vendors.nvidia.internal_protocols import NvmlDeviceHandle


__all__ = (
    "preflight_nvml_control_record",
    "nvml_original_matches",
    "invoke_nvml_prepared_member",
    "nvml_target_matches",
    "read_nvml_control_member",
    "nvml_goal_matches",
    "nvml_precondition_matches",
)


def preflight_nvml_control_record(
    module: NvmlControlModuleProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    *,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    goal: Literal["requested", "original"],
) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
    native_failures: tuple[type[Exception], ...] = (
        module.NVMLError,
        ctypes.ArgumentError,
        *HANDLED_RUNTIME_EXCEPTIONS,
    )
    try:
        bound = acquire_nvml_physical_binding(module, target=prepared.target)
        for member in record.members:
            if member.backend != "nvml":
                continue
            observed = read_nvml_control_member(
                module, bound.handle, member, record, resolver, goal
            )
            if not nvml_precondition_matches(member, observed, goal):
                failures = (
                    () if observed.conversion_failure is None else (observed.conversion_failure,)
                )
                return (
                    GPUControlPreflightRejection(
                        "native_state_changed", "NVML original or conversion authority changed."
                    ),
                    failures,
                )
            if not nvml_goal_matches(member, observed, goal):
                require_nvml_member_actuators(member, resolver, module.NVMLError, goal=goal)
    except native_failures as exception:
        return (
            GPUControlPreflightRejection("native_query_failed", "NVML native preflight failed."),
            (exception,),
        )
    return None, ()


def nvml_original_matches(member: GPURecoveryMember, observation: NvmlControlObservation) -> bool:
    return (
        observation.user_meaning_verified
        and observation.original_restorable
        and (observation.value, observation.mode)
        == (
            member.original_value,
            member.original_mode,
        )
    )


def invoke_nvml_prepared_member(
    module: NvmlControlModuleProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    member: GPURecoveryMember,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    if member.member_id == "application_clocks":
        return invoke_nvml_application_pair(
            module, record, prepared, recovery, token, member, resolver, goal
        )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared, (GPUControlMemberResult(member, None, None, None),), (), True
        )
    native_failures: tuple[type[Exception], ...] = (
        module.NVMLError,
        ctypes.ArgumentError,
        *HANDLED_RUNTIME_EXCEPTIONS,
    )
    try:
        bound = acquire_nvml_physical_binding(module, target=prepared.target)
        current = read_nvml_control_member(module, bound.handle, member, record, resolver, goal)
    except native_failures as exception:
        return GPUControlMemberInvocation(
            prepared,
            (_outcome(member, None, False, "native_query_failed", goal),),
            (exception,),
            False,
        )
    if not nvml_precondition_matches(member, current, goal):
        conversion_failures = (
            () if current.conversion_failure is None else (current.conversion_failure,)
        )
        return GPUControlMemberInvocation(
            prepared,
            (_outcome(member, None, False, "native_state_changed", goal),),
            conversion_failures,
            False,
        )
    if nvml_goal_matches(member, current, goal):
        return GPUControlMemberInvocation(
            prepared, (_outcome(member, current, False, None, goal),), (), False
        )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared, (GPUControlMemberResult(member, None, None, None),), (), True
        )
    prepared = recovery.before_effect(prepared, recovery_member_key(member))
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared, (GPUControlMemberResult(member, None, None, None),), (), True
        )
    try:
        bound = acquire_nvml_physical_binding(module, target=prepared.target)
        current = read_nvml_control_member(module, bound.handle, member, record, resolver, goal)
        require_nvml_member_actuators(member, resolver, module.NVMLError, goal=goal)
    except native_failures as exception:
        return GPUControlMemberInvocation(
            prepared,
            (_outcome(member, None, False, "native_query_failed", goal),),
            (exception,),
            False,
        )
    if not nvml_precondition_matches(member, current, goal):
        conversion_failures = (
            () if current.conversion_failure is None else (current.conversion_failure,)
        )
        return GPUControlMemberInvocation(
            prepared,
            (_outcome(member, None, False, "native_state_changed", goal),),
            conversion_failures,
            False,
        )
    if nvml_goal_matches(member, current, goal):
        return GPUControlMemberInvocation(
            prepared, (_outcome(member, current, False, None, goal),), (), False
        )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared, (GPUControlMemberResult(member, None, None, None),), (), True
        )
    invoked = True
    failures: list[Exception] = []
    code = None
    observation = None
    try:
        invoke_nvml_member_actuator(module, bound.handle, member, resolver, goal)
    except NvmlClockOffsetError as exception:
        invoked = exception.actuator_invoked
        code = "native_control_failed"
        failures.append(exception)
    except native_failures as exception:
        code = "native_control_failed"
        failures.append(exception)
    if invoked:
        try:
            bound = acquire_nvml_physical_binding(module, target=prepared.target)
            observation = read_nvml_control_member(
                module, bound.handle, member, record, resolver, goal
            )
        except native_failures as exception:
            code = "native_query_failed"
            failures.append(exception)
        else:
            if observation.conversion_failure is not None:
                failures.append(observation.conversion_failure)
            if code is None and not nvml_goal_matches(member, observation, goal):
                code = "native_readback_mismatch"
    return GPUControlMemberInvocation(
        prepared, (_outcome(member, observation, invoked, code, goal),), tuple(failures), False
    )


def nvml_target_matches(member: GPURecoveryMember, observed: NvmlControlObservation) -> bool:
    return (
        observed.user_meaning_verified
        and (member.requested_value is None or member.requested_value == observed.value)
        and (member.requested_mode is None or member.requested_mode == observed.mode)
    )


def read_nvml_control_member(
    module: NvmlControlModuleProtocol,
    handle: NvmlDeviceHandle,
    member: GPURecoveryMember,
    record: GPURecoveryRecord,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    goal: Literal["requested", "original"],
) -> NvmlControlObservation:
    if member.member_id == "application_clocks":
        pair = application_clock_members(record)
        return read_nvml_application_observations(module, handle, record, goal)[pair.index(member)]
    if goal == "original":
        if member.field == "power_limit":
            return read_nvml_original_power_member(module, handle, member)
        if member.field == "fan_speed":
            return read_nvml_original_fan_member(module, handle, member, record)
        if member.field in ("core_clock", "mem_clock"):
            return read_nvml_original_clock_member(module, handle, member, resolver)
        if member.field == "persistence_mode":
            return read_nvml_original_persistence_member(module, handle, member)
    elif goal != "requested":
        raise ValidationError("NVML read requires an explicit native goal.")
    if member.field == "power_limit":
        return read_nvml_power_member(module, handle, member, record)
    if member.field == "fan_speed":
        return read_nvml_fan_member(module, handle, member, record)
    if member.field in ("core_clock", "mem_clock"):
        return read_nvml_clock_member(module, handle, member, record, resolver)
    if member.field == "persistence_mode":
        return read_nvml_persistence_member(module, handle, member)
    raise ValidationError("NVML member has no declared native control owner.")


def _outcome(
    member: GPURecoveryMember,
    observed: NvmlControlObservation | None,
    invoked: bool,
    failure: str | None,
    goal: Literal["requested", "original"],
) -> GPUControlMemberResult:
    evidence = (
        None
        if observed is None
        else NativeMemberObservation(
            observed.value, observed.mode, nvml_goal_matches(member, observed, goal)
        )
    )
    return build_native_member_result(member, evidence, invoked, failure, goal)


def nvml_goal_matches(
    member: GPURecoveryMember,
    observed: NvmlControlObservation,
    goal: Literal["requested", "original"],
) -> bool:
    if goal == "original":
        return nvml_original_matches(member, observed)
    return nvml_target_matches(member, observed)


def nvml_precondition_matches(
    member: GPURecoveryMember,
    observed: NvmlControlObservation,
    goal: Literal["requested", "original"],
) -> bool:
    if goal == "original":
        return observed.original_restorable
    return nvml_original_matches(member, observed)

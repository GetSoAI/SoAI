"""SoAI - Receipt-bound paired NVML application-clock execution [backend/hardware/vendors/nvidia/nvml_application_clock_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from dataclasses import replace
from typing import Literal

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    GPUPreparedControl,
    NativeMemberObservation,
)
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.protocols import GPUControlRecoveryProtocol
from core.validation.strict_numbers import require_positive_int_strict
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import build_native_member_result
from hardware.vendors.nvidia.internal_protocols import (
    NvmlControlModuleProtocol,
    NvmlControlObservation,
    NvmlNativeFunctionResolverProtocol,
)
from hardware.vendors.nvidia.nvml_actuator_acquisition import require_nvml_member_actuators
from hardware.vendors.nvidia.nvml_application_clock_preparation import (
    application_clock_members,
    read_nvml_application_observations,
    require_nvml_application_module,
)
from hardware.vendors.nvidia.nvml_physical_binding import (
    NvmlBoundDevice,
    acquire_nvml_physical_binding,
)

__all__ = ("invoke_nvml_application_pair",)


def invoke_nvml_application_pair(
    module: NvmlControlModuleProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    selected: GPURecoveryMember,
    resolver: NvmlNativeFunctionResolverProtocol | None,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    members = application_clock_members(record)
    if selected not in members:
        raise ValidationError("NVML application invocation omits its selected member.")
    native_failures: tuple[type[Exception], ...] = (
        module.NVMLError,
        ctypes.ArgumentError,
        *HANDLED_RUNTIME_EXCEPTIONS,
    )
    bound: NvmlBoundDevice | None = None
    for checkpointed in (False, True):
        if token.thread_event.is_set():
            return GPUControlMemberInvocation(
                prepared,
                tuple(GPUControlMemberResult(member, None, None, None) for member in members),
                (),
                True,
            )
        if checkpointed:
            for member in members:
                prepared = recovery.before_effect(prepared, recovery_member_key(member))
        try:
            bound = acquire_nvml_physical_binding(module, target=prepared.target)
            observations = read_nvml_application_observations(module, bound.handle, record, goal)
            if not all(
                _safe(member, observed, goal)
                for member, observed in zip(members, observations, strict=True)
            ):
                return GPUControlMemberInvocation(
                    prepared,
                    tuple(
                        _result(member, observed, False, "native_state_changed", goal)
                        for member, observed in zip(members, observations, strict=True)
                    ),
                    (),
                    False,
                )
            if all(
                _matches(member, observed, goal)
                for member, observed in zip(members, observations, strict=True)
            ):
                return GPUControlMemberInvocation(
                    prepared,
                    tuple(
                        _result(member, observed, False, None, goal)
                        for member, observed in zip(members, observations, strict=True)
                    ),
                    (),
                    False,
                )
            for member in members:
                require_nvml_member_actuators(member, resolver, module.NVMLError, goal=goal)
        except native_failures as exception:
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    _result(member, None, False, "native_query_failed", goal) for member in members
                ),
                (exception,),
                False,
            )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared,
            tuple(GPUControlMemberResult(member, None, None, None) for member in members),
            (),
            True,
        )
    if bound is None:
        raise ValidationError("NVML application invocation lost its physical binding.")
    failures: list[Exception] = []
    code = None
    try:
        application = require_nvml_application_module(module)
        values = tuple(
            require_positive_int_strict(
                member.original_value if goal == "original" else member.requested_value,
                error_message="NVML application native target is invalid.",
            )
            for member in members
        )
        application.nvmlDeviceSetApplicationsClocks(bound.handle, values[1], values[0])
    except native_failures as exception:
        failures.append(exception)
        code = "native_control_failed"
    try:
        bound = acquire_nvml_physical_binding(module, target=prepared.target)
        observations = read_nvml_application_observations(module, bound.handle, record, goal)
    except native_failures as exception:
        failures.append(exception)
        outcomes = tuple(
            _result(member, None, True, "native_query_failed", goal) for member in members
        )
    else:
        outcomes = tuple(
            _result(
                member,
                observed,
                True,
                (
                    code
                    if code is not None
                    else (None if _matches(member, observed, goal) else "native_readback_mismatch")
                ),
                goal,
            )
            for member, observed in zip(members, observations, strict=True)
        )
    return GPUControlMemberInvocation(
        prepared, outcomes, tuple(failures), token.thread_event.is_set()
    )


def _matches(
    member: GPURecoveryMember,
    observed: NvmlControlObservation,
    goal: Literal["requested", "original"],
) -> bool:
    target = member.original_value if goal == "original" else member.requested_value
    return (
        observed.user_meaning_verified
        and observed.original_restorable
        and observed.value == target
        and observed.mode is None
    )


def _safe(
    member: GPURecoveryMember,
    observed: NvmlControlObservation,
    goal: Literal["requested", "original"],
) -> bool:
    return (
        observed.original_restorable
        if goal == "original"
        else _matches(member, observed, "original")
    )


def _result(
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
            observed.value, observed.mode, _matches(member, observed, goal)
        )
    )
    result = build_native_member_result(member, evidence, invoked, failure, goal)
    if observed is None:
        return result
    complete_success = (
        invoked
        and failure is None
        and observed.user_meaning_verified
        and observed.original_restorable
    )
    preserved_peer = (
        member.original_value == member.requested_value == observed.value
        and member.changed is False
        and observed.mode is None
    )
    if complete_success and preserved_peer:
        result = replace(result, recovery_member=replace(result.recovery_member, changed=False))
    return result

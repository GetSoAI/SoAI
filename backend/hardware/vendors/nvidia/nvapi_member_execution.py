"""SoAI - NvAPI native member invocation and exact reconciliation evidence [backend/hardware/vendors/nvidia/nvapi_member_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    NativeMemberObservation,
)
from core.system.privileges import is_admin
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import build_native_member_result
from hardware.vendors.nvidia.nvapi_clock_controls import NvApiClockActuation
from hardware.vendors.nvidia.nvapi_control_observations import (
    nvapi_member_goal_matches,
    nvapi_member_is_safe,
    prepare_nvapi_member_invocation,
)
from hardware.vendors.nvidia.nvapi_fan_controls import NvApiFanActuation
from hardware.vendors.nvidia.nvapi_function_acquisition import (
    require_nvapi_native_success,
)
from hardware.vendors.nvidia.nvapi_power_controls import NvApiPowerActuation

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_control_types import GPUPreparedControl
    from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
    from core.hardware.protocols import GPUControlRecoveryProtocol
    from core.system.protocols import CommandExecutorProtocol
    from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
    from hardware.vendors.nvidia.internal_protocols import NvmlControlModuleProtocol
    from hardware.vendors.nvidia.nvapi_control_observation import NvApiControlObservation

__all__ = ("invoke_nvapi_prepared_member",)


def invoke_nvapi_prepared_member(
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    member: GPURecoveryMember,
    *,
    executable: GpuExecutableResolution,
    query_interface: Callable[[int], int | None],
    nvml_module: NvmlControlModuleProtocol | None,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    footprint = (
        tuple(
            member if recovery_member_key(row) == recovery_member_key(member) else row
            for row in record.members
            if row.backend == "nvapi" and row.field == "fan_speed"
        )
        if member.field == "fan_speed"
        else (member,)
    )
    if is_admin() is not True:
        return GPUControlMemberInvocation(
            prepared,
            tuple(
                build_native_member_result(row, None, False, "native_permission_required", goal)
                for row in footprint
            ),
            (StateError("NvAPI control requires administrator privileges."),),
            False,
        )
    native_failures: tuple[type[Exception], ...] = (
        ctypes.ArgumentError,
        *HANDLED_RUNTIME_EXCEPTIONS,
    )
    handle: ctypes.c_void_p | None = None
    action: NvApiFanActuation | NvApiClockActuation | NvApiPowerActuation | None = None
    for checkpointed in (False, True):
        if token.thread_event.is_set():
            return GPUControlMemberInvocation(
                prepared,
                tuple(GPUControlMemberResult(row, None, None, None) for row in footprint),
                (),
                True,
            )
        if checkpointed:
            for row in footprint:
                prepared = recovery.before_effect(prepared, recovery_member_key(row))
        try:
            observations = tuple(
                prepare_nvapi_member_invocation(
                    executor,
                    record,
                    prepared.target,
                    row,
                    executable=executable,
                    query_interface=query_interface,
                    nvml_module=nvml_module,
                    goal=goal,
                    purpose="observe",
                )[1]
                for row in footprint
            )
            handle, _, action = prepare_nvapi_member_invocation(
                executor,
                record,
                prepared.target,
                member,
                executable=executable,
                query_interface=query_interface,
                nvml_module=nvml_module,
                goal=goal,
                purpose="stage",
            )
        except native_failures as exception:
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(row, None, False, "native_query_failed", goal)
                    for row in footprint
                ),
                (exception,),
                False,
            )
        if not all(
            nvapi_member_is_safe(row, observed, goal)
            for row, observed in zip(footprint, observations, strict=True)
        ):
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(
                        row,
                        NativeMemberObservation(
                            observed.value,
                            observed.mode,
                            nvapi_member_goal_matches(row, observed, goal),
                        ),
                        False,
                        "native_state_changed",
                        goal,
                    )
                    for row, observed in zip(footprint, observations, strict=True)
                ),
                tuple(
                    observed.conversion_failure
                    for observed in observations
                    if observed.conversion_failure is not None
                ),
                False,
            )
        if action is None:
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(
                        row,
                        NativeMemberObservation(
                            observed.value,
                            observed.mode,
                            nvapi_member_goal_matches(row, observed, goal),
                        ),
                        False,
                        (
                            None
                            if nvapi_member_goal_matches(row, observed, goal)
                            else "native_policy_unavailable"
                        ),
                        goal,
                    )
                    for row, observed in zip(footprint, observations, strict=True)
                ),
                (),
                False,
            )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared,
            tuple(GPUControlMemberResult(row, None, None, None) for row in footprint),
            (),
            True,
        )
    if is_admin() is not True:
        return GPUControlMemberInvocation(
            prepared,
            tuple(
                build_native_member_result(row, None, False, "native_permission_required", goal)
                for row in footprint
            ),
            (StateError("NvAPI control requires administrator privileges."),),
            False,
        )
    if action is None or handle is None:
        raise ValidationError("NvAPI invocation lost its staged actuator authority.")
    failures: list[Exception] = []
    failure = None
    try:
        if isinstance(action, NvApiFanActuation):
            status = action.setter(handle, ctypes.pointer(action.buffer))
        elif isinstance(action, NvApiClockActuation):
            status = action.setter(handle, ctypes.pointer(action.buffer))
        else:
            status = action.setter(handle, ctypes.pointer(action.buffer))
        require_nvapi_native_success(status, actuator_invoked=True)
    except native_failures as exception:
        failures.append(exception)
        failure = "native_control_failed"
    outcomes: list[GPUControlMemberResult] = []
    for row in footprint:
        readback: NvApiControlObservation | None = None
        read_failure = failure
        try:
            _, readback, _ = prepare_nvapi_member_invocation(
                executor,
                record,
                prepared.target,
                row,
                executable=executable,
                query_interface=query_interface,
                nvml_module=nvml_module,
                goal=goal,
                purpose="observe",
            )
        except native_failures as exception:
            failures.append(exception)
            read_failure = "native_query_failed"
        else:
            if readback.conversion_failure is not None:
                failures.append(readback.conversion_failure)
            if read_failure is None and not nvapi_member_goal_matches(row, readback, goal):
                read_failure = "native_readback_mismatch"
        outcomes.append(
            build_native_member_result(
                row,
                (
                    NativeMemberObservation(
                        readback.value,
                        readback.mode,
                        nvapi_member_goal_matches(row, readback, goal),
                    )
                    if readback is not None
                    else None
                ),
                True,
                read_failure,
                goal,
            )
        )
    complete_fan_success = (
        isinstance(action, NvApiFanActuation)
        and not failures
        and all(outcome.failure_code is None for outcome in outcomes)
    )
    for index, (row, outcome) in enumerate(zip(footprint, outcomes, strict=True)):
        changed = outcome.recovery_member.changed
        unchanged_fan_peer = (
            complete_fan_success
            and row.changed is False
            and (row.original_value, row.original_mode)
            == (row.requested_value, row.requested_mode)
            == (outcome.observed_value, outcome.observed_mode)
        )
        if row.changed is True:
            changed = True
        elif row.changed is None or unchanged_fan_peer:
            changed = None if row.changed is None else False
        outcomes[index] = replace(
            outcome, recovery_member=replace(outcome.recovery_member, changed=changed)
        )
    return GPUControlMemberInvocation(
        prepared, tuple(outcomes), tuple(failures), token.thread_event.is_set()
    )

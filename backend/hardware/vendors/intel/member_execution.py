"""SoAI - Intel paired configured-frequency invocation and original reconciliation [backend/hardware/vendors/intel/member_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError, ValidationError
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
from core.runtime.protocols import RuntimePlatformViewProtocol
from core.system.protocols import CommandExecutorProtocol
from core.validation.strict_integer import is_strict_int
from hardware.gpu_inventory.executable_resolution import GpuExecutableResolution
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import build_native_member_result
from hardware.vendors.intel.i915_member_execution import (
    invoke_i915_prepared_member,
    preflight_i915_control_record,
)
from hardware.vendors.intel.native_control_observations import (
    IntelNativeControlState,
    intel_frequency_footprint,
    read_intel_frequency_pair,
)

__all__ = (
    "preflight_intel_control_record",
    "invoke_intel_prepared_member",
)


def preflight_intel_control_record(
    executor: CommandExecutorProtocol,
    *,
    executable: GpuExecutableResolution,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    goal: Literal["requested", "original"],
) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
    if any(member.backend == "intel_i915" for member in record.members):
        rejection, failures = preflight_i915_control_record(record, prepared, goal=goal)
        if rejection is not None or failures:
            return rejection, failures
    try:
        for member in record.members:
            if member.backend != "intel_xpum":
                continue
            _, _, observations, safe = read_intel_frequency_pair(
                executor,
                executable,
                record,
                prepared.target,
                member,
                goal=goal,
            )
            if not safe or len(observations) != 2:
                return (
                    GPUControlPreflightRejection(
                        "native_state_changed",
                        "Intel configured relation or original changed.",
                    ),
                    (),
                )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        return GPUControlPreflightRejection(
            "native_query_failed",
            "Intel configured native preflight failed.",
        ), (exception,)
    return None, ()


def invoke_intel_prepared_member(
    executor: CommandExecutorProtocol,
    *,
    executable: GpuExecutableResolution,
    runtime_platform: RuntimePlatformViewProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    member: GPURecoveryMember,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    if member.backend == "intel_i915":
        return invoke_i915_prepared_member(record, prepared, recovery, token, member, goal=goal)
    if not isinstance(runtime_platform.is_windows, bool):
        raise ValidationError("Intel native invocation platform authority is invalid.")
    footprint = intel_frequency_footprint(record, member)
    unattempted = tuple(GPUControlMemberResult(item, None, None, None) for item in footprint)
    observations: tuple[NativeMemberObservation, ...] = ()
    state: IntelNativeControlState | None = None
    for checkpointed in (False, True):
        if token.thread_event.is_set():
            return GPUControlMemberInvocation(
                prepared,
                unattempted,
                (),
                True,
            )
        if checkpointed:
            for item in footprint:
                prepared = recovery.before_effect(prepared, recovery_member_key(item))
        try:
            state, _, observations, safe = read_intel_frequency_pair(
                executor,
                executable,
                record,
                prepared.target,
                member,
                goal=goal,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            query_failures = tuple(
                build_native_member_result(item, None, False, "native_query_failed", goal)
                for item in footprint
            )
            return GPUControlMemberInvocation(prepared, query_failures, (exception,), False)
        if not safe:
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(item, observed, False, "native_state_changed", goal)
                    for item, observed in zip(footprint, observations, strict=True)
                ),
                (),
                False,
            )
        if all(observed.target_matched for observed in observations):
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(item, observed, False, None, goal)
                    for item, observed in zip(footprint, observations, strict=True)
                ),
                (),
                False,
            )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared,
            unattempted,
            (),
            True,
        )
    if state is None or executable.path is None:
        raise ValidationError("Intel invocation lost its actual native query authority.")
    values = tuple(
        item.original_value if goal == "original" else item.requested_value for item in footprint
    )
    failures: list[Exception] = []
    failure = None
    try:
        result = executor.execute(
            [
                executable.path,
                "config",
                "-d",
                str(state.native_device_id),
                "-t",
                str(member.domain_id),
                "--frequencyrange",
                f"{values[0]},{values[1]}",
            ],
            timeout=5,
            shell=False,
            use_sudo=not runtime_platform.is_windows,
        )
        if (
            not is_strict_int(result.return_code)
            or not isinstance(result.stdout, str)
            or not isinstance(result.stderr, str)
        ):
            raise ValidationError("Intel paired actuator response is invalid.")
        if result.return_code != 0:
            raise StateError(
                "Intel paired native actuator failed after invocation.",
                details={
                    "native_device_id": state.native_device_id,
                    "tile_id": member.domain_id,
                    "frequency_range": f"{values[0]},{values[1]}",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.return_code,
                    "actuator_invoked": True,
                },
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_control_failed"
    readback: tuple[NativeMemberObservation, ...] = ()
    try:
        _, _, readback, _ = read_intel_frequency_pair(
            executor,
            executable,
            record,
            prepared.target,
            member,
            goal=goal,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_query_failed"
    outcomes = tuple(
        build_native_member_result(
            item,
            readback[index] if readback else None,
            True,
            failure
            or (
                "native_readback_mismatch"
                if readback and not readback[index].target_matched
                else None
            ),
            goal,
        )
        for index, item in enumerate(footprint)
    )
    cancelled = token.thread_event.is_set()
    if (
        goal == "requested"
        and failure is None
        and not cancelled
        and readback
        and all(observed.target_matched for observed in readback)
    ):
        outcomes = tuple(
            (
                replace(outcome, recovery_member=replace(outcome.recovery_member, changed=False))
                if (item.requested_value, item.requested_mode)
                == (item.original_value, item.original_mode)
                and (observed.value, observed.mode) == (item.original_value, item.original_mode)
                else outcome
            )
            for item, observed, outcome in zip(footprint, observations, outcomes, strict=True)
        )
    return GPUControlMemberInvocation(prepared, outcomes, tuple(failures), cancelled)

"""SoAI - AMD native member actuation and exact original reconciliation [backend/hardware/vendors/amd/member_execution.py]"""
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
)
from core.hardware.gpu_recovery_records import (
    GPUEffectState,
    GPURecoveryMember,
    GPURecoveryRecord,
    GPUVerificationState,
)
from core.hardware.protocols import GPUControlRecoveryProtocol
from core.system.protocols import CommandExecutorProtocol
from core.validation.strict_integer import is_strict_int
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import (
    build_native_member_result,
    build_native_query_failure_invocation,
)
from hardware.vendors.amd.control_member_observations import AmdMemberState, read_amd_member_state

__all__ = (
    "preflight_amd_control_record",
    "invoke_amd_prepared_member",
)


def preflight_amd_control_record(
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    *,
    goal: Literal["requested", "original"],
) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
    try:
        for member in record.members:
            if member.backend not in ("amd_smi", "amd_overdrive"):
                continue
            state = read_amd_member_state(
                executor, record, prepared.target, member, goal=goal, stage=False
            )
            if not state.safe:
                return (
                    GPUControlPreflightRejection(
                        "native_state_changed", "AMD native original or conversion changed."
                    ),
                    (),
                )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        return GPUControlPreflightRejection(
            "native_query_failed", "AMD native preflight failed."
        ), (exception,)
    return None, ()


def invoke_amd_prepared_member(
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    compound_clock = member.backend == "amd_overdrive" and member.field in (
        "core_clock",
        "mem_clock",
    )
    footprint = (
        tuple(
            member if recovery_member_key(item) == recovery_member_key(member) else item
            for item in record.members
            if item.backend == "amd_overdrive" and item.field in ("core_clock", "mem_clock")
        )
        if compound_clock
        else (member,)
    )
    if member not in footprint:
        raise ValidationError("AMD commit footprint omitted its selected frozen member.")
    states: tuple[AmdMemberState, ...] = ()
    for checkpointed in (False, True):
        if token.thread_event.is_set():
            return GPUControlMemberInvocation(
                prepared,
                tuple(GPUControlMemberResult(item, None, None, None) for item in footprint),
                (),
                True,
            )
        if checkpointed:
            for item in footprint:
                prepared = recovery.before_effect(prepared, recovery_member_key(item))
        try:
            states = tuple(
                read_amd_member_state(
                    executor, record, prepared.target, item, goal=goal, stage=True
                )
                for item in footprint
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            return build_native_query_failure_invocation(prepared, footprint, exception, goal)
        if not all(state.safe for state in states):
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(
                        item, state.observation, False, "native_state_changed", goal
                    )
                    for item, state in zip(footprint, states, strict=True)
                ),
                (),
                False,
            )
        if all(state.observation.target_matched for state in states):
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(item, state.observation, False, None, goal)
                    for item, state in zip(footprint, states, strict=True)
                ),
                (),
                False,
            )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared,
            tuple(GPUControlMemberResult(item, None, None, None) for item in footprint),
            (),
            True,
        )
    commands = states[0].commands
    if compound_clock:
        commands = tuple(state.commands[0] for state in states) + (states[0].commands[1],)
    failures: list[Exception] = []
    failure = None
    try:
        for path, payload in commands:
            result = executor.execute(
                ["sh", "-c", 'printf "%s\\n" "$1" > "$2"', "soai-amd-control", payload, path],
                timeout=5,
                shell=False,
                use_sudo=True,
            )
            if (
                not is_strict_int(result.return_code)
                or not isinstance(result.stdout, str)
                or not isinstance(result.stderr, str)
            ):
                raise ValidationError("AMD native actuator response is invalid.")
            if result.return_code != 0:
                raise StateError(
                    "AMD native actuator failed after invocation.",
                    details={
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "return_code": result.return_code,
                        "actuator_invoked": True,
                        "sysfs_path": path,
                        "native_payload": payload,
                    },
                )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_control_failed"
    outcomes: list[GPUControlMemberResult] = []
    for item in footprint:
        observed = None
        read_failure = failure
        try:
            observed = read_amd_member_state(
                executor, record, prepared.target, item, goal=goal, stage=True
            ).observation
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failures.append(exception)
            read_failure = "native_query_failed"
        else:
            if not observed.target_matched and read_failure is None:
                read_failure = "native_readback_mismatch"
        outcomes.append(build_native_member_result(item, observed, True, read_failure, goal))
    if (
        goal == "requested"
        and compound_clock
        and not token.thread_event.is_set()
        and not failures
        and all(
            outcome.failure_code is None
            and outcome.recovery_member.verification == GPUVerificationState.MATCHED
            for outcome in outcomes
        )
    ):
        outcomes = [
            (
                replace(outcome, recovery_member=replace(outcome.recovery_member, changed=False))
                if item.requested_value == item.original_value
                and state.observation.value == item.original_value
                and outcome.recovery_member.effect == GPUEffectState.APPLIED
                else outcome
            )
            for item, state, outcome in zip(footprint, states, outcomes, strict=True)
        ]
    return GPUControlMemberInvocation(prepared, tuple(outcomes), tuple(failures), False)

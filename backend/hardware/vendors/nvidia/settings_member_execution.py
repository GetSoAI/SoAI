"""SoAI - NVIDIA settings member actuation and original reconciliation [backend/hardware/vendors/nvidia/settings_member_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    GPUPreparedControl,
)
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.protocols import GPUControlRecoveryProtocol
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import (
    build_native_member_result,
)
from hardware.vendors.nvidia.settings_control_observations import (
    SettingsMemberState,
    read_settings_member_state,
)
from hardware.vendors.nvidia.settings_control_queries import (
    NvidiaSettingsSession,
    invoke_settings_attribute,
)

__all__ = (
    "preflight_settings_control_record",
    "invoke_settings_prepared_member",
)


def preflight_settings_control_record(
    session: NvidiaSettingsSession,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    *,
    goal: Literal["requested", "original"],
) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
    try:
        for member in record.members:
            if member.backend != "nvidia_settings":
                continue
            state = read_settings_member_state(
                session, record, prepared.target, member, goal=goal, stage=False
            )
            if not state.safe:
                return (
                    GPUControlPreflightRejection(
                        "native_state_changed", "NVIDIA settings original or conversion changed."
                    ),
                    (),
                )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        return GPUControlPreflightRejection(
            "native_query_failed", "NVIDIA settings native preflight failed."
        ), (exception,)
    return None, ()


def invoke_settings_prepared_member(
    session: NvidiaSettingsSession,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    footprint: tuple[GPURecoveryMember, ...] = (member,)
    if member.member_id == "gpu_fan_policy":
        footprint += tuple(
            item
            for item in record.members
            if item.backend == "nvidia_settings"
            and item.field == "fan_speed"
            and item.member_id.startswith("fan:")
        )
    state: SettingsMemberState | None = None
    for checkpointed in (False, True):
        if token.thread_event.is_set():
            return GPUControlMemberInvocation(
                prepared,
                tuple(GPUControlMemberResult(affected, None, None, None) for affected in footprint),
                (),
                True,
            )
        if checkpointed:
            for affected in footprint:
                prepared = recovery.before_effect(prepared, recovery_member_key(affected))
        try:
            states = tuple(
                read_settings_member_state(
                    session,
                    record,
                    prepared.target,
                    affected,
                    goal=goal,
                    stage=member.member_id != "gpu_fan_policy",
                )
                for affected in footprint
            )
            state = states[0]
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(affected, None, False, "native_query_failed", goal)
                    for affected in footprint
                ),
                (exception,),
                False,
            )
        if not all(observed.safe for observed in states):
            return GPUControlMemberInvocation(
                prepared,
                tuple(
                    build_native_member_result(
                        affected, observed.observation, False, "native_state_changed", goal
                    )
                    for affected, observed in zip(footprint, states, strict=True)
                ),
                (),
                False,
            )
        if state.observation.target_matched:
            return GPUControlMemberInvocation(
                prepared,
                (build_native_member_result(member, state.observation, False, None, goal),),
                (),
                False,
            )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared,
            tuple(GPUControlMemberResult(affected, None, None, None) for affected in footprint),
            (),
            True,
        )
    if state is None:
        raise ValidationError("NVIDIA settings invocation lost its staged observation.")
    if state.native_target is None:
        return GPUControlMemberInvocation(
            prepared,
            (
                build_native_member_result(
                    member, state.observation, False, "native_policy_unavailable", goal
                ),
            ),
            (),
            False,
        )
    failures: list[Exception] = []
    failure = None
    try:
        invoke_settings_attribute(session, target=state.target, value=state.native_target)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_control_failed"
    outcomes: list[GPUControlMemberResult] = []
    for affected in footprint:
        observation = None
        read_failure = failure
        try:
            observation = read_settings_member_state(
                session, record, prepared.target, affected, goal=goal, stage=True
            ).observation
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            failures.append(exception)
            read_failure = "native_query_failed"
        else:
            if not observation.target_matched and affected == member and read_failure is None:
                read_failure = "native_readback_mismatch"
        outcomes.append(build_native_member_result(affected, observation, True, read_failure, goal))
    if not outcomes:
        raise ValidationError("NVIDIA settings invocation lost its actual actuator footprint.")
    return GPUControlMemberInvocation(
        prepared, tuple(outcomes), tuple(failures), token.thread_event.is_set()
    )

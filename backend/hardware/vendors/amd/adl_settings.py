"""SoAI - ADL native clock member planning and exact configured observations [backend/hardware/vendors/amd/adl_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    GPUPreparedControl,
    NativeMemberObservation,
)
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import (
    GPUEffectState,
    GPUOriginalObservationState,
    GPURecoveryMember,
    GPURecoveryPhase,
    GPURecoveryRecord,
    GPURestorationState,
    GPUVerificationState,
)
from core.types.json import JSONDict
from core.validation.strict_integer import is_strict_int
from core.validation.strict_numbers import require_int_in_range_strict
from hardware.gpu_tuning.control_recovery_records import recovery_member_key, require_record_target
from hardware.gpu_tuning.native_control_results import build_native_member_result
from hardware.vendors.amd.adl_abi import AdlControlObservation
from hardware.vendors.amd.adl_capabilities import bind_adl_controls, require_adl_clock_observation

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.protocols import GPUControlRecoveryProtocol
    from core.system.protocols import CommandExecutorProtocol
    from hardware.vendors.amd.adl_session import AdlSession


__all__ = (
    "prepare_adl_clock_members",
    "observe_adl_clock_member",
    "prepare_adl_control_record",
    "preflight_adl_control_record",
    "invoke_adl_prepared_member",
)


def prepare_adl_clock_members(
    observation: AdlControlObservation,
    *,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
) -> tuple[GPURecoveryMember, ...]:
    if (
        not requested_settings
        or not set(requested_settings).issubset({"core_clock", "mem_clock"})
        or set(requested_settings) != set(requested_modes)
        or any(mode not in ("auto", "manual") for mode in requested_modes.values())
    ):
        raise ValidationError("ADL preparation requires complete selected clock fields and modes.")
    members: list[GPURecoveryMember] = []
    for field, requested in requested_settings.items():
        feature = require_adl_clock_observation(observation, field)
        bounds = observation.features[feature.index]
        if requested_modes[field] == "auto":
            if requested != "auto" and (
                not is_strict_int(requested) or requested != bounds.default
            ):
                raise ValidationError(
                    "ADL automatic clock conflicts with its actual native default."
                )
            native_target = bounds.default
        else:
            native_target = require_int_in_range_strict(
                requested,
                minimum=bounds.minimum,
                maximum=bounds.maximum,
                error_message="ADL clock target is outside its actual native range.",
            )
        members.append(
            GPURecoveryMember(
                field=field,
                member_id=f"od8:{feature.index}",
                domain_id=None,
                pstate_id=None,
                original_value=observation.current[feature.index],
                original_mode=None,
                native_unit="MHz",
                original_observation=GPUOriginalObservationState.OBSERVED,
                effect=GPUEffectState.NOT_ATTEMPTED,
                verification=GPUVerificationState.NOT_ATTEMPTED,
                restoration=GPURestorationState.NOT_REQUIRED,
                backend="amd_adl",
                changed=False,
                requested_value=native_target,
                requested_mode=None,
            )
        )
    return tuple(members)


def observe_adl_clock_member(
    observation: AdlControlObservation,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> tuple[NativeMemberObservation, bool]:
    if goal not in ("requested", "original"):
        raise ValidationError("ADL observation requires its explicit frozen native goal.")
    feature = require_adl_clock_observation(observation, member.field)
    routing_valid = (
        member.backend == "amd_adl"
        and member.member_id == f"od8:{feature.index}"
        and member.native_unit == "MHz"
        and member.domain_id is None
        and member.pstate_id is None
    )
    values_valid = (
        member.original_mode is None
        and member.requested_mode is None
        and is_strict_int(member.original_value)
        and is_strict_int(member.requested_value)
        and member.original_observation == GPUOriginalObservationState.OBSERVED
    )
    if not routing_valid or not values_valid:
        raise ValidationError("ADL frozen member does not match its native clock quantity.")
    native = observation.features[feature.index]
    original = require_int_in_range_strict(
        member.original_value,
        minimum=1,
        maximum=2**31 - 1,
        error_message="ADL original clock is invalid.",
    )
    requested = require_int_in_range_strict(
        member.requested_value,
        minimum=1,
        maximum=2**31 - 1,
        error_message="ADL requested clock is invalid.",
    )
    target = original if goal == "original" else requested
    current = observation.current[feature.index]
    target_safe = native.minimum <= target <= native.maximum
    original_safe = native.minimum <= original <= native.maximum
    matched = target_safe and current == target
    safe = target_safe and (goal == "original" or original_safe and current == original)
    return NativeMemberObservation(current, None, matched), safe


def prepare_adl_control_record(
    session: AdlSession,
    executor: CommandExecutorProtocol,
    *,
    target: GPUPhysicalDevice,
    operation_id: str,
    requested_settings: JSONDict,
    requested_modes: JSONDict,
) -> GPURecoveryRecord:
    observation = bind_adl_controls(session, executor, target)
    members = prepare_adl_clock_members(
        observation, requested_settings=requested_settings, requested_modes=requested_modes
    )
    return GPURecoveryRecord(
        operation_id=operation_id,
        device_id=target.device_id,
        physical_identity=target.identity,
        backend="amd_adl",
        phase=GPURecoveryPhase.PREPARED,
        requested_settings=copy.deepcopy(requested_settings),
        requested_modes=copy.deepcopy(requested_modes),
        requested_units={field: "MHz" for field in requested_settings},
        members=members,
        pci_bdf_observations=target.pci_bdf_observations,
        commit_intent=None,
    )


def preflight_adl_control_record(
    session: AdlSession,
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
    try:
        require_record_target(record, prepared.target)
        observation = bind_adl_controls(session, executor, prepared.target)
        if any(
            not observe_adl_clock_member(observation, member, goal="requested")[1]
            for member in record.members
            if member.backend == "amd_adl"
        ):
            return (
                GPUControlPreflightRejection(
                    "native_state_changed", "ADL frozen native original or range changed."
                ),
                (),
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        return GPUControlPreflightRejection(
            "native_query_failed", "ADL native preflight failed."
        ), (exception,)
    return None, ()


def invoke_adl_prepared_member(
    session: AdlSession,
    executor: CommandExecutorProtocol,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    require_record_target(record, prepared.target)
    if member not in record.members:
        raise ValidationError("ADL invocation requires its exact frozen native member.")
    observation: AdlControlObservation | None = None
    for checkpointed in (False, True):
        if token.thread_event.is_set():
            return GPUControlMemberInvocation(
                prepared, (GPUControlMemberResult(member, None, None, None),), (), True
            )
        if checkpointed:
            prepared = recovery.before_effect(prepared, recovery_member_key(member))
        try:
            observation = bind_adl_controls(session, executor, prepared.target)
            observed, safe = observe_adl_clock_member(observation, member, goal=goal)
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            return GPUControlMemberInvocation(
                prepared,
                (build_native_member_result(member, None, False, "native_query_failed", goal),),
                (exception,),
                False,
            )
        if not safe:
            return GPUControlMemberInvocation(
                prepared,
                (
                    build_native_member_result(
                        member, observed, False, "native_state_changed", goal
                    ),
                ),
                (),
                False,
            )
        if observed.target_matched:
            return GPUControlMemberInvocation(
                prepared,
                (build_native_member_result(member, observed, False, None, goal),),
                (),
                False,
            )
    if token.thread_event.is_set():
        return GPUControlMemberInvocation(
            prepared, (GPUControlMemberResult(member, None, None, None),), (), True
        )
    if observation is None:
        raise ValidationError("ADL invocation lost its physical observation.")
    feature = require_adl_clock_observation(observation, member.field)
    target_value = member.original_value if goal == "original" else member.requested_value
    if not is_strict_int(target_value):
        raise ValidationError("ADL frozen actuator requires a native integer target.")
    failures: list[Exception] = []
    failure = None
    try:
        status = session.write_clock(observation, feature.index, target_value)
        if status != 0:
            raise StateError(
                "ADL native actuator failed after invocation.",
                details={"native_status": status, "actuator_invoked": True},
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_control_failed"
    configured = None
    try:
        configured = observe_adl_clock_member(
            bind_adl_controls(session, executor, prepared.target), member, goal=goal
        )[0]
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_query_failed"
    else:
        if not configured.target_matched and failure is None:
            failure = "native_readback_mismatch"
    return GPUControlMemberInvocation(
        prepared,
        (build_native_member_result(member, configured, True, failure, goal),),
        tuple(failures),
        False,
    )

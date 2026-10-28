"""SoAI - Durable i915 maximum invocation and original readback [backend/hardware/vendors/intel/i915_member_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import replace
from typing import Literal

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import StateError, ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    GPUPreparedControl,
    NativeMemberObservation,
)
from core.hardware.gpu_recovery_records import GPURecoveryMember, GPURecoveryRecord
from core.hardware.protocols import GPUControlRecoveryProtocol
from core.validation.strict_integer import is_strict_int
from hardware.gpu_tuning.control_recovery_records import recovery_member_key
from hardware.gpu_tuning.native_control_results import (
    build_native_member_result,
    build_native_query_failure_invocation,
)
from hardware.vendors.intel.i915_frequency import (
    I915FrequencyState,
    read_i915_frequency_pair,
)

__all__ = (
    "preflight_i915_control_record",
    "invoke_i915_prepared_member",
)


def preflight_i915_control_record(
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    *,
    goal: Literal["requested", "original"],
) -> tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]]:
    try:
        members = tuple(member for member in record.members if member.backend == "intel_i915")
        if len(members) != 2:
            raise ValidationError(
                "i915 preflight requires its complete configured GT0 frequency footprint."
            )
        maximum = tuple(item for item in members if item.member_id == "frequency:max")
        if len(maximum) != 1:
            raise ValidationError("i915 preflight requires its actual maximum endpoint.")
        member = maximum[0]
        state, _, observations = read_i915_frequency_pair(
            record, prepared.target, member, goal=goal
        )
        _require_i915_goal(state, member, goal)
        if not observations[1].target_matched and not state.writable:
            raise PermissionError("i915 configured maximum is not writable.")
        if goal == "requested" and (
            not observations[0].target_matched
            or state.maximum_mhz
            not in (
                member.original_value,
                member.requested_value,
            )
        ):
            raise StateError("i915 configured maximum changed before its prepared request.")
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        return GPUControlPreflightRejection(
            "native_state_changed", "i915 configured physical goal is unavailable."
        ), (exception,)
    return None, ()


def _require_i915_goal(
    state: I915FrequencyState,
    member: GPURecoveryMember,
    goal: Literal["requested", "original"],
) -> int:
    desired = member.original_value if goal == "original" else member.requested_value
    if not is_strict_int(desired) or not state.minimum_mhz <= desired <= state.upper_bound_mhz:
        raise ValidationError("i915 configured goal conflicts with its actual native bounds.")
    return desired


def invoke_i915_prepared_member(
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    token: CancellationTokenProtocol,
    member: GPURecoveryMember,
    *,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    footprint = tuple(
        item
        for endpoint in ("frequency:min", "frequency:max")
        for item in record.members
        if item.backend == "intel_i915" and item.member_id == endpoint
    )
    if len(footprint) != 2 or member not in footprint:
        raise ValidationError("i915 invocation requires its exact complete GT0 footprint.")
    maximum_member = footprint[1]
    unattempted = GPUControlMemberInvocation(
        prepared,
        tuple(GPUControlMemberResult(item, None, None, None) for item in footprint),
        (),
        True,
    )
    if token.thread_event.is_set():
        return unattempted
    try:
        before, _, observations = read_i915_frequency_pair(
            record, prepared.target, member, goal=goal
        )
        desired = _require_i915_goal(before, maximum_member, goal)
        if goal == "requested" and (
            not observations[0].target_matched
            or before.maximum_mhz
            not in (maximum_member.original_value, maximum_member.requested_value)
        ):
            raise StateError("i915 configured frequency changed before its prepared request.")
        if observations[1].target_matched:
            outcomes = tuple(
                build_native_member_result(
                    item,
                    observed,
                    False,
                    None if observed.target_matched else "native_readback_mismatch",
                    goal,
                )
                for item, observed in zip(footprint, observations, strict=True)
            )
            return GPUControlMemberInvocation(prepared, outcomes, (), False)
        if not before.writable:
            raise PermissionError("i915 configured maximum is not writable.")
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        return build_native_query_failure_invocation(prepared, footprint, exception, goal)
    if token.thread_event.is_set():
        return unattempted
    for item in footprint:
        prepared = recovery.before_effect(prepared, recovery_member_key(item))
    try:
        state, _, _ = read_i915_frequency_pair(record, prepared.target, member, goal=goal)
        _require_i915_goal(state, maximum_member, goal)
        if not state.writable:
            raise PermissionError("i915 configured maximum became unwritable before effect.")
        if (
            state.card_directory,
            state.device_directory,
            state.gt_directory,
            state.minimum_mhz,
            state.maximum_mhz,
            state.upper_bound_mhz,
        ) != (
            before.card_directory,
            before.device_directory,
            before.gt_directory,
            before.minimum_mhz,
            before.maximum_mhz,
            before.upper_bound_mhz,
        ):
            raise StateError("i915 physical mapping or configured bounds changed before effect.")
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        return GPUControlMemberInvocation(
            prepared,
            tuple(
                build_native_member_result(item, None, False, "native_state_changed", goal)
                for item in footprint
            ),
            (exception,),
            False,
        )
    if token.thread_event.is_set():
        return replace(unattempted, prepared=prepared)
    failures: list[Exception] = []
    failure: str | None = None
    try:
        with open_text(
            os.path.join(state.gt_directory, "rps_max_freq_mhz"), mode="w", encoding="utf-8"
        ) as handle:
            text = f"{desired}\n"
            if handle.write(text) != len(text):
                raise StateError("i915 maximum write did not consume its complete requested value.")
            handle.flush()
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_control_failed"
    readback: tuple[NativeMemberObservation, ...] = ()
    try:
        _, _, readback = read_i915_frequency_pair(record, prepared.target, member, goal=goal)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        failures.append(exception)
        failure = "native_query_failed"
    completed: list[GPUControlMemberResult] = []
    for index, endpoint in enumerate(footprint):
        observed_endpoint = readback[index] if readback else None
        endpoint_failure = failure
        if endpoint_failure is None and observed_endpoint is not None:
            if not observed_endpoint.target_matched:
                endpoint_failure = "native_readback_mismatch"
        completed.append(
            build_native_member_result(endpoint, observed_endpoint, True, endpoint_failure, goal)
        )
    outcomes = tuple(completed)
    if goal == "requested" and failure is None and readback and readback[0].target_matched:
        outcomes = (
            replace(
                outcomes[0], recovery_member=replace(outcomes[0].recovery_member, changed=False)
            ),
            outcomes[1],
        )
    return GPUControlMemberInvocation(
        prepared, outcomes, tuple(failures), token.thread_event.is_set()
    )

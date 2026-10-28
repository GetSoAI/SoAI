"""SoAI - Complete receipt-bound native operation outcomes [backend/hardware/gpu_tuning/native_operation_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    GPUControlResult,
    GPUPreparedControl,
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
from core.hardware.protocols import GPUControlRecoveryProtocol
from core.logging.protocols import TraceLogger
from hardware.gpu_tuning.control_recovery_records import (
    recovery_member_key,
    require_application_targets,
    require_record_target,
)
from hardware.gpu_tuning.control_recovery_serialization import recovery_scope_digest
from hardware.gpu_tuning.native_control_results import (
    merge_native_member_invocation,
    reduce_gpu_control_result,
)

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import GPUControlMemberKey

OPERATION_HARDWARE_GPU_EXECUTE_NATIVE_CONTROL = "hardware.gpu.execute_native_control"


__all__ = (
    "execute_native_control_record",
    "execute_native_original_record",
)


def execute_native_control_record(
    *,
    target: GPUPhysicalDevice,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    cancellation_token: CancellationTokenProtocol,
    logger: TraceLogger,
    preflight: Callable[
        [GPURecoveryRecord, GPUPreparedControl],
        tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]],
    ],
    invoke_member: Callable[
        [
            GPURecoveryRecord,
            GPUPreparedControl,
            GPUControlRecoveryProtocol,
            CancellationTokenProtocol,
            GPURecoveryMember,
        ],
        GPUControlMemberInvocation,
    ],
) -> tuple[GPUControlResult, GPUPreparedControl]:
    record = copy.deepcopy(record)
    require_record_target(record, target)
    require_application_targets(record)
    if recovery_scope_digest(record) != prepared.scope_digest or any(
        member.backend is None
        or member.effect != GPUEffectState.NOT_ATTEMPTED
        or member.changed is not False
        for member in record.members
    ):
        raise ValidationError("Native invocation requires its complete frozen zero-effect plan.")
    outcomes = tuple(GPUControlMemberResult(member, None, None, None) for member in record.members)
    result = _result(record, target, outcomes, ())
    reduce_gpu_control_result(result, prepared=prepared)
    if cancellation_token.thread_event.is_set():
        result = replace(result, failure_codes=("operation_cancelled",))
        return result, recovery.record_result(prepared, result)
    rejection, native_failures = preflight(record, prepared)
    if rejection is not None and not isinstance(rejection, GPUControlPreflightRejection):
        raise ValidationError("Native preflight requires an explicit typed zero-effect rejection.")
    if not isinstance(native_failures, tuple) or any(
        not isinstance(failure, Exception) for failure in native_failures
    ):
        raise ValidationError("Native preflight requires immutable private failures.")
    failures = list(native_failures)
    if rejection is None and failures:
        raise ValidationError(
            "Native preflight cannot certify a plan with unresolved query failures.",
            cause=ExceptionGroup("Native preflight failures", failures),
        )
    if rejection is not None:
        if failures:
            _report_failures(logger, record, failures)
        result = _result(record, target, outcomes, (rejection.code,))
        return result, recovery.record_result(prepared, result)
    codes: tuple[str, ...] = ()
    completed: set[GPUControlMemberKey] = set()
    for member in record.members:
        if recovery_member_key(member) in completed:
            continue
        invocation = invoke_member(record, prepared, recovery, cancellation_token, member)
        if not isinstance(invocation, GPUControlMemberInvocation):
            raise ValidationError("Native member invocation requires its typed actual outcome.")
        require_record_target(record, invocation.prepared.target)
        if (
            invocation.prepared.operation_id != record.operation_id
            or invocation.prepared.scope_digest != recovery_scope_digest(record)
        ):
            raise ValidationError("Native invocation changed its prepared immutable scope.")
        prepared = invocation.prepared
        if invocation.failures:
            _report_failures(logger, record, list(invocation.failures))
        if invocation.cancelled:
            codes = ("operation_cancelled",)
        outcomes, member_complete = merge_native_member_invocation(
            record, member, outcomes, invocation, goal="requested"
        )
        member_failures = tuple(
            outcome.failure_code
            for outcome in invocation.member_results
            if outcome.failure_code is not None
        )
        codes = tuple(dict.fromkeys((*codes, *member_failures)))
        result = _result(record, target, outcomes, codes)
        reduce_gpu_control_result(result, prepared=prepared)
        completed.update(member_complete)
        prepared = recovery.record_result(prepared, result)
        if invocation.cancelled or member_failures:
            break
    if cancellation_token.thread_event.is_set():
        codes = tuple(dict.fromkeys((*codes, "operation_cancelled")))
    result = _result(record, target, outcomes, codes)
    return result, recovery.record_result(prepared, result)


def execute_native_original_record(
    *,
    target: GPUPhysicalDevice,
    record: GPURecoveryRecord,
    prepared: GPUPreparedControl,
    recovery: GPUControlRecoveryProtocol,
    cancellation_token: CancellationTokenProtocol,
    logger: TraceLogger,
    original_member_order: tuple[GPUControlMemberKey, ...],
    preflight: Callable[
        [GPURecoveryRecord, GPUPreparedControl],
        tuple[GPUControlPreflightRejection | None, tuple[Exception, ...]],
    ],
    invoke_member: Callable[
        [
            GPURecoveryRecord,
            GPUPreparedControl,
            GPUControlRecoveryProtocol,
            CancellationTokenProtocol,
            GPURecoveryMember,
        ],
        GPUControlMemberInvocation,
    ],
) -> tuple[GPUControlResult, GPUPreparedControl]:
    record = copy.deepcopy(record)
    require_record_target(record, target)
    if (
        record.phase != GPURecoveryPhase.RECONCILING
        or recovery_scope_digest(record) != prepared.scope_digest
        or any(
            member.backend is None
            or member.original_observation != GPUOriginalObservationState.OBSERVED
            or (member.original_value is None and member.original_mode is None)
            for member in record.members
        )
    ):
        raise ValidationError("Native original reconciliation requires complete frozen originals.")
    replace(prepared, member_keys=original_member_order)
    actual_keys = tuple(recovery_member_key(member) for member in record.members)
    if not isinstance(original_member_order, tuple) or len(original_member_order) != len(
        actual_keys
    ):
        raise ValidationError("Original reconciliation requires immutable complete member order.")
    if (
        any(key not in actual_keys for key in original_member_order)
        or len(set(original_member_order)) != len(original_member_order)
        or set(original_member_order) != set(actual_keys)
        or set(original_member_order) != set(prepared.member_keys)
    ):
        raise ValidationError(
            "Original reconciliation requires the exact native member permutation."
        )
    outcomes = tuple(
        GPUControlMemberResult(
            replace(
                member,
                verification=GPUVerificationState.UNAVAILABLE,
                restoration=GPURestorationState.UNAVAILABLE,
            ),
            None,
            None,
            None,
        )
        for member in record.members
    )
    result = _result(record, target, outcomes, ())
    reduce_gpu_control_result(result, prepared=prepared)
    if cancellation_token.thread_event.is_set():
        result = replace(result, failure_codes=("operation_cancelled",))
        return result, recovery.record_result(prepared, result)
    rejection, native_failures = preflight(record, prepared)
    if rejection is not None and not isinstance(rejection, GPUControlPreflightRejection):
        raise ValidationError("Original preflight requires its typed invocation rejection.")
    if not isinstance(native_failures, tuple) or any(
        not isinstance(failure, Exception) for failure in native_failures
    ):
        raise ValidationError("Original preflight requires immutable private failures.")
    if rejection is None and native_failures:
        raise ValidationError(
            "Original preflight cannot certify unresolved queries.",
            cause=ExceptionGroup("Native original preflight failures", list(native_failures)),
        )
    if rejection is not None:
        if native_failures:
            _report_failures(logger, record, list(native_failures))
        result = _result(record, target, outcomes, (rejection.code,))
        return result, recovery.record_result(prepared, result)
    codes: tuple[str, ...] = ()
    completed: set[GPUControlMemberKey] = set()
    for member_key in original_member_order:
        if member_key in completed:
            continue
        position = actual_keys.index(member_key)
        member = record.members[position]
        invocation = invoke_member(record, prepared, recovery, cancellation_token, member)
        if not isinstance(invocation, GPUControlMemberInvocation):
            raise ValidationError("Original native invocation requires its typed member outcome.")
        require_record_target(record, invocation.prepared.target)
        if (
            invocation.prepared.operation_id != record.operation_id
            or invocation.prepared.scope_digest != recovery_scope_digest(record)
        ):
            raise ValidationError("Native invocation changed its prepared immutable scope.")
        prepared = invocation.prepared
        if invocation.failures:
            _report_failures(logger, record, list(invocation.failures))
        if invocation.cancelled:
            codes = tuple(dict.fromkeys((*codes, "operation_cancelled")))
        outcomes, member_complete = merge_native_member_invocation(
            record, member, outcomes, invocation, goal="original"
        )
        member_failures = tuple(
            outcome.failure_code
            for outcome in invocation.member_results
            if outcome.failure_code is not None
        )
        codes = tuple(dict.fromkeys((*codes, *member_failures)))
        result = _result(record, target, outcomes, codes)
        reduce_gpu_control_result(result, prepared=prepared)
        completed.update(member_complete)
        prepared = recovery.record_result(prepared, result)
    if cancellation_token.thread_event.is_set():
        codes = tuple(dict.fromkeys((*codes, "operation_cancelled")))
    result = _result(record, target, outcomes, codes)
    return result, recovery.record_result(prepared, result)


def _result(
    record: GPURecoveryRecord,
    target: GPUPhysicalDevice,
    outcomes: tuple[GPUControlMemberResult, ...],
    codes: tuple[str, ...],
) -> GPUControlResult:
    return GPUControlResult(
        record.operation_id, target, outcomes, tuple(record.requested_settings), (), codes
    )


def _report_failures(
    logger: TraceLogger, record: GPURecoveryRecord, failures: list[Exception]
) -> None:
    cause = (
        failures[0]
        if len(failures) == 1
        else ExceptionGroup("GPU native operation failures", failures)
    )
    error = StateError(
        "GPU native control operation did not complete.",
        operation="hardware.gpu.execute_native_control",
        details={"operation_id": record.operation_id, "device_id": record.device_id},
        cause=cause,
    )
    log_exception(
        logger,
        error,
        message="GPU native control operation did not complete (non-critical).",
        operation=OPERATION_HARDWARE_GPU_EXECUTE_NATIVE_CONTROL,
        details={"operation_id": record.operation_id, "device_id": record.device_id},
        level="trace",
    )

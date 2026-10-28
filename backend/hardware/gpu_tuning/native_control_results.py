"""SoAI - Native GPU member evidence and result reduction [backend/hardware/gpu_tuning/native_control_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import (
    GPUControlMemberInvocation,
    GPUControlMemberResult,
    GPUControlReduction,
    GPUControlResult,
    GPUPreparedControl,
)
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import (
    GPUEffectState,
    GPUOriginalObservationState,
    GPURecoveryMember,
    GPURecoveryRecord,
    GPURestorationState,
    GPUVerificationState,
)
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_number, require_optional_bool
from core.validation.strict_numbers import require_optional_non_negative_int_strict
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_tuning.control_recovery_records import recovery_member_key

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import NativeMemberObservation
    from core.hardware.gpu_recovery_records import GPUControlMemberKey

__all__ = ("reduce_gpu_control_result", "build_native_query_failure_invocation")


def reduce_gpu_control_result(
    result: GPUControlResult, *, prepared: GPUPreparedControl
) -> GPUControlReduction:
    if not isinstance(result, GPUControlResult) or not isinstance(prepared, GPUPreparedControl):
        raise ValidationError("GPU native outcome requires its prepared authority.")
    _validate_result_scope(result, prepared)
    keys = tuple(_validate_member(member) for member in result.members)
    if not keys or len(set(keys)) != len(keys) or set(keys) != set(prepared.member_keys):
        raise ValidationError("GPU native outcome does not cover the prepared native members.")
    if set(result.requested_fields) != {key[1] for key in keys}:
        raise ValidationError("GPU native outcome requested fields conflict with prepared members.")
    changed_values = tuple(member.recovery_member.changed for member in result.members)
    known_changed = any(value is True for value in changed_values)
    unknown_changed = any(value is None for value in changed_values)
    changed = True if known_changed else (None if unknown_changed else False)
    requested_verified = all(
        member.recovery_member.verification == GPUVerificationState.MATCHED
        for member in result.members
    )
    failed = bool(result.failure_codes) or any(
        member.failure_code is not None for member in result.members
    )
    unresolved = unknown_changed or any(_member_unresolved(member) for member in result.members)
    if failed and known_changed:
        unresolved = True
    return GPUControlReduction(
        changed=changed,
        unresolved=unresolved,
        requested_verified=requested_verified,
        persistence_eligible=requested_verified and not unresolved and not failed,
    )


def build_native_member_result(
    member: GPURecoveryMember,
    observed: NativeMemberObservation | None,
    invoked: bool,
    failure: str | None,
    goal: Literal["requested", "original"],
) -> GPUControlMemberResult:
    if goal not in ("requested", "original") or not isinstance(invoked, bool):
        raise ValidationError("Native member result requires explicit invocation and goal.")
    if observed is not None and not isinstance(observed.target_matched, bool):
        raise ValidationError("Native member observation requires explicit target verification.")
    matched = observed is not None and observed.target_matched
    changed = None if invoked else False
    if (
        invoked
        and observed is not None
        and (observed.value, observed.mode) != (member.original_value, member.original_mode)
    ):
        changed = True
    effect = (
        (GPUEffectState.FAILED if failure is not None else GPUEffectState.APPLIED)
        if invoked
        else GPUEffectState.NOT_ATTEMPTED
    )
    verification = (
        GPUVerificationState.MATCHED
        if matched
        else (
            GPUVerificationState.MISMATCHED
            if observed is not None
            else (
                GPUVerificationState.UNAVAILABLE if invoked else GPUVerificationState.NOT_ATTEMPTED
            )
        )
    )
    restoration = (
        GPURestorationState.PENDING if invoked and not matched else GPURestorationState.NOT_REQUIRED
    )
    if goal == "original":
        changed = (
            True
            if member.changed is True
            else (None if member.changed is None or invoked else False)
        )
        effect = member.effect if not invoked else effect
        verification = GPUVerificationState.UNAVAILABLE
        restoration = GPURestorationState.RESTORED if matched else GPURestorationState.UNAVAILABLE
    updated = replace(
        member, effect=effect, verification=verification, restoration=restoration, changed=changed
    )
    return GPUControlMemberResult(
        updated,
        observed.value if observed is not None else None,
        observed.mode if observed is not None else None,
        failure,
    )


def build_native_query_failure_invocation(
    prepared: GPUPreparedControl,
    members: tuple[GPURecoveryMember, ...],
    exception: Exception,
    goal: Literal["requested", "original"],
) -> GPUControlMemberInvocation:
    return GPUControlMemberInvocation(
        prepared,
        tuple(
            build_native_member_result(member, None, False, "native_query_failed", goal)
            for member in members
        ),
        (exception,),
        False,
    )


def _validate_result_scope(result: GPUControlResult, prepared: GPUPreparedControl) -> None:
    require_canonical_trimmed_json_text(
        result.operation_id, error_message="GPU native operation identifier is invalid."
    )
    if result.operation_id != prepared.operation_id:
        raise ValidationError("GPU native operation does not match prepared authority.")
    if not isinstance(result.target, GPUPhysicalDevice) or not _same_physical_scope(
        result.target, prepared.target
    ):
        raise ValidationError("GPU native target does not match prepared physical authority.")
    for field in result.requested_fields:
        require_canonical_trimmed_json_text(
            field, error_message="GPU native requested field is invalid."
        )
    if not result.requested_fields or len(set(result.requested_fields)) != len(
        result.requested_fields
    ):
        raise ValidationError("GPU native outcome requires distinct requested fields.")
    for message in result.messages:
        if not isinstance(message, str):
            raise ValidationError("GPU native messages require text.")
    for failure_code in result.failure_codes:
        require_canonical_trimmed_json_text(
            failure_code, error_message="GPU native failure code is invalid."
        )


def _same_physical_scope(target: GPUPhysicalDevice, expected: GPUPhysicalDevice) -> bool:
    target_uuid = target.identity.uuid
    expected_uuid = expected.identity.uuid
    target_pci = target.identity.pci_bdf_full
    expected_pci = expected.identity.pci_bdf_full
    return (
        target.device_id == expected.device_id
        and target.vendor.casefold() == expected.vendor.casefold()
        and (target_uuid.casefold() if target_uuid is not None else None)
        == (expected_uuid.casefold() if expected_uuid is not None else None)
        and (normalize_observed_full_pci_bdf(target_pci) if target_pci is not None else None)
        == (normalize_observed_full_pci_bdf(expected_pci) if expected_pci is not None else None)
        and target.pci_bdf_observations == expected.pci_bdf_observations
        and target.identity.native_device_path == expected.identity.native_device_path
        and target.identity.windows_pnp_instance_id == expected.identity.windows_pnp_instance_id
    )


def _validate_member(result: GPUControlMemberResult) -> GPUControlMemberKey:
    if not isinstance(result, GPUControlMemberResult):
        raise ValidationError("GPU native member outcome is invalid.")
    member = result.recovery_member
    if not isinstance(member, GPURecoveryMember):
        raise ValidationError("GPU native member evidence is invalid.")
    if member.backend is None:
        raise ValidationError("GPU native outcome requires explicit member backend routing.")
    for text in (member.backend, member.field, member.member_id, member.native_unit):
        require_canonical_trimmed_json_text(
            text, error_message="GPU native member scope is invalid."
        )
    domain = require_optional_non_negative_int_strict(
        member.domain_id, error_message="GPU native member domain is invalid."
    )
    pstate = require_optional_non_negative_int_strict(
        member.pstate_id, error_message="GPU native member Pstate is invalid."
    )
    changed = require_optional_bool(
        member.changed, label="GPU native changed", build_error=ValidationError
    )
    if not isinstance(member.effect, GPUEffectState) or not isinstance(
        member.verification, GPUVerificationState
    ):
        raise ValidationError("GPU native effect or verification state is invalid.")
    if not isinstance(member.restoration, GPURestorationState) or not isinstance(
        member.original_observation, GPUOriginalObservationState
    ):
        raise ValidationError("GPU native restoration or original observation state is invalid.")
    if member.effect == GPUEffectState.NOT_ATTEMPTED and changed is not False:
        raise ValidationError("GPU native unattempted member requires known zero effect.")
    for value in (member.original_value, member.requested_value, result.observed_value):
        if value is not None:
            require_number(
                value, label="GPU native scalar observation", build_error=ValidationError
            )
    for mode in (member.original_mode, member.requested_mode, result.observed_mode):
        _validate_mode(mode)
    original_present = member.original_value is not None or member.original_mode is not None
    if (member.original_observation == GPUOriginalObservationState.OBSERVED) != original_present:
        raise ValidationError("GPU native original observation conflicts with its evidence.")
    if (
        member.restoration == GPURestorationState.RESTORED
        and member.original_observation != GPUOriginalObservationState.OBSERVED
    ):
        raise ValidationError("GPU native restoration requires recorded original evidence.")
    if member.verification == GPUVerificationState.MATCHED and not _requested_target_matches(
        result
    ):
        raise ValidationError("GPU native matched verification requires its frozen native target.")
    if result.failure_code is not None:
        require_canonical_trimmed_json_text(
            result.failure_code, error_message="GPU native member failure code is invalid."
        )
    return member.backend, member.field, member.member_id, domain, pstate


def _requested_target_matches(result: GPUControlMemberResult) -> bool:
    member = result.recovery_member
    if member.requested_value is None and member.requested_mode is None:
        return False
    if member.requested_value is not None and result.observed_value != member.requested_value:
        return False
    return member.requested_mode is None or result.observed_mode == member.requested_mode


def _validate_mode(mode: int | str | None) -> None:
    if mode is None or is_strict_int(mode):
        return
    require_canonical_trimmed_json_text(
        mode, error_message="GPU native mode observation is invalid."
    )


def _member_unresolved(result: GPUControlMemberResult) -> bool:
    member = result.recovery_member
    return (
        member.changed is None
        or member.verification
        in (
            GPUVerificationState.MISMATCHED,
            GPUVerificationState.UNAVAILABLE,
            GPUVerificationState.FAILED,
        )
        or (member.changed is True and member.verification == GPUVerificationState.NOT_ATTEMPTED)
        or member.restoration
        not in (GPURestorationState.NOT_REQUIRED, GPURestorationState.RESTORED)
    )


def merge_native_member_invocation(
    record: GPURecoveryRecord,
    selected: GPURecoveryMember,
    outcomes: tuple[GPUControlMemberResult, ...],
    invocation: GPUControlMemberInvocation,
    *,
    goal: Literal["requested", "original"],
) -> tuple[tuple[GPUControlMemberResult, ...], frozenset[GPUControlMemberKey]]:
    actual_keys = tuple(recovery_member_key(member) for member in record.members)
    invocation_keys = tuple(
        recovery_member_key(outcome.recovery_member) for outcome in invocation.member_results
    )
    if recovery_member_key(selected) not in invocation_keys:
        raise ValidationError("Native footprint result omitted its selected member.")
    updated = list(outcomes)
    for member_key, outcome in zip(invocation_keys, invocation.member_results, strict=True):
        if member_key not in actual_keys:
            raise ValidationError("Native footprint result has an unprepared member.")
        position = actual_keys.index(member_key)
        original = record.members[position]
        frozen = replace(
            outcome.recovery_member,
            effect=original.effect,
            verification=original.verification,
            restoration=original.restoration,
            changed=original.changed,
        )
        if frozen != original:
            raise ValidationError(
                "Native footprint result changed its frozen originals or targets."
            )
        previous = updated[position].recovery_member
        if previous.changed is True and outcome.recovery_member.changed is not True:
            raise ValidationError("Native footprint result erased an established prior effect.")
        updated[position] = outcome
    completed = frozenset(
        member_key
        for member_key, outcome in zip(invocation_keys, invocation.member_results, strict=True)
        if outcome.failure_code is None
        and (
            goal == "requested"
            and outcome.recovery_member.verification == GPUVerificationState.MATCHED
            or goal == "original"
            and (outcome.observed_value, outcome.observed_mode)
            == (outcome.recovery_member.original_value, outcome.recovery_member.original_mode)
            and outcome.recovery_member.restoration
            in (GPURestorationState.RESTORED, GPURestorationState.NOT_REQUIRED)
        )
    )
    return tuple(updated), completed

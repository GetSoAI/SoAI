"""SoAI - GPU prepared control receipts and outcomes [backend/core/hardware/gpu_control_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.path_coercion import coerce_path
from core.hardware.gpu_control_operation_types import GPUControlCommitIntent
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_recovery_records import GPURecoveryMember
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_optional_non_negative_int_strict,
)
from core.validation.strings import require_canonical_trimmed_json_text

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import (
        GPUControlMemberKey,
        GPURecoveryRecord,
        GPUStartupLegacyRecoveryRecord,
        GPUStartupRecoveryRecord,
    )
    from core.types.json import JSONDict


__all__ = (
    "GPUSlotReadState",
    "GPUSlotReadFailure",
    "GPUSlotReadError",
    "GPUSlotWriteFailure",
    "GPUSlotWriteError",
    "GPUControlMemberResult",
    "NativeMemberObservation",
    "GPUControlResult",
    "GPUControlDirtyMarkerReceipt",
    "GPUPreparedControl",
    "GPUControlCommitAcknowledgement",
    "GPUControlMemberInvocation",
    "GPUControlReduction",
    "GPUSlotReadResult",
    "GPURecoveryAdmissionState",
    "GPURecoveryAdmission",
    "GPUControlStartupDisposition",
    "GPUControlStartupResult",
)


class GPUSlotReadState(StrEnum):
    ABSENT = "absent"
    VALID = "valid"


class GPUSlotReadFailure(StrEnum):
    UNAVAILABLE = "unavailable"
    PERMISSION_DENIED = "permission_denied"
    MALFORMED = "malformed"
    UNSUPPORTED_FORMAT = "unsupported_format"


class GPUSlotReadError(StateError):
    def __init__(self, reason: GPUSlotReadFailure) -> None:
        self.reason = reason
        super().__init__(
            "GPU slot metadata could not be read safely.",
            operation="hardware.gpu_slots.read",
            details={"reason": reason.value},
        )


class GPUSlotWriteFailure(StrEnum):
    INVALID_PAYLOAD = "invalid_payload"
    UNAVAILABLE = "unavailable"
    PERMISSION_DENIED = "permission_denied"
    PERSISTENCE_UNCERTAIN = "persistence_uncertain"
    REVISION_CONFLICT = "revision_conflict"


class GPUSlotWriteError(StateError):
    def __init__(self, reason: GPUSlotWriteFailure) -> None:
        self.reason = reason
        super().__init__(
            "GPU slot metadata could not be persisted safely.",
            operation="hardware.gpu_slots.write",
            details={"reason": reason.value},
        )


@dataclass(frozen=True, slots=True)
class GPUControlMemberResult:
    recovery_member: GPURecoveryMember
    observed_value: int | float | None
    observed_mode: int | str | None
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class GPUControlResult:
    operation_id: str
    target: GPUPhysicalDevice
    members: tuple[GPUControlMemberResult, ...]
    requested_fields: tuple[str, ...]
    messages: tuple[str, ...]
    failure_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, tuple)
            for value in (self.members, self.requested_fields, self.messages, self.failure_codes)
        ):
            raise ValidationError("GPU native result collections require immutable tuples.")


@dataclass(frozen=True, slots=True)
class GPUControlDirtyMarkerReceipt:
    marker_path: str
    file_device: int
    file_inode: int

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.marker_path, error_message="GPU dirty marker path is invalid."
        )
        coerce_path(self.marker_path)
        require_non_negative_int_strict(
            self.file_device, error_message="GPU dirty marker device identity is invalid."
        )
        require_non_negative_int_strict(
            self.file_inode, error_message="GPU dirty marker inode identity is invalid."
        )


@dataclass(frozen=True, slots=True)
class GPUPreparedControl:
    operation_id: str
    target: GPUPhysicalDevice
    member_keys: tuple[GPUControlMemberKey, ...]
    scope_digest: str
    store_revision: str
    dirty_marker_receipt: GPUControlDirtyMarkerReceipt | None

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.operation_id, error_message="GPU prepared operation identifier is invalid."
        )
        if not isinstance(self.target, GPUPhysicalDevice):
            raise ValidationError("GPU preparation requires a physical target.")
        require_canonical_sha256_hexdigest(self.scope_digest, label="GPU prepared scope digest")
        require_canonical_sha256_hexdigest(self.store_revision, label="GPU prepared store revision")
        if self.dirty_marker_receipt is not None and not isinstance(
            self.dirty_marker_receipt, GPUControlDirtyMarkerReceipt
        ):
            raise ValidationError("GPU prepared dirty marker correlation is invalid.")
        if not isinstance(self.member_keys, tuple) or not self.member_keys:
            raise ValidationError("GPU preparation requires immutable native member keys.")
        for key in self.member_keys:
            if not isinstance(key, tuple) or len(key) != 5:
                raise ValidationError("GPU prepared native member key is invalid.")
            for routing_text in key[:3]:
                require_canonical_trimmed_json_text(
                    routing_text,
                    error_message="GPU prepared native member key requires explicit routing.",
                )
            for member_locator in key[3:]:
                require_optional_non_negative_int_strict(
                    member_locator,
                    error_message="GPU prepared native member domain or Pstate is invalid.",
                )
        if len(set(self.member_keys)) != len(self.member_keys):
            raise ValidationError("GPU preparation contains duplicate native member keys.")


@dataclass(frozen=True, slots=True)
class GPUControlCommitAcknowledgement:
    prepared: GPUPreparedControl
    commit_intent: GPUControlCommitIntent
    committed_revision: str
    committed_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.prepared, GPUPreparedControl):
            raise ValidationError("GPU commit acknowledgement requires its prepared receipt.")
        if not isinstance(self.commit_intent, GPUControlCommitIntent):
            raise ValidationError("GPU commit acknowledgement requires frozen user intent.")
        require_canonical_sha256_hexdigest(
            self.committed_revision, label="GPU committed store revision"
        )
        require_canonical_trimmed_json_text(
            self.committed_at, error_message="GPU committed timestamp is invalid."
        )


@dataclass(frozen=True, slots=True)
class GPUControlMemberInvocation:
    prepared: GPUPreparedControl
    member_results: tuple[GPUControlMemberResult, ...]
    failures: tuple[Exception, ...]
    cancelled: bool

    def __post_init__(self) -> None:
        if not isinstance(self.prepared, GPUPreparedControl):
            raise ValidationError("GPU native invocation requires its prepared receipt.")
        if (
            not isinstance(self.member_results, tuple)
            or not self.member_results
            or any(not isinstance(result, GPUControlMemberResult) for result in self.member_results)
            or any(
                not isinstance(result.recovery_member, GPURecoveryMember)
                for result in self.member_results
            )
        ):
            raise ValidationError("GPU native invocation requires its complete member results.")
        native_keys: list[GPUControlMemberKey] = []
        for result in self.member_results:
            member = result.recovery_member
            if member.backend is None:
                raise ValidationError("GPU native invocation requires explicit backend routing.")
            native_keys.append(
                (member.backend, member.field, member.member_id, member.domain_id, member.pstate_id)
            )
        keys = tuple(native_keys)
        replace(self.prepared, member_keys=keys)
        if len(set(keys)) != len(keys) or not set(keys).issubset(self.prepared.member_keys):
            raise ValidationError("GPU native invocation has duplicate or foreign member routing.")
        if not isinstance(self.failures, tuple) or any(
            not isinstance(failure, Exception) for failure in self.failures
        ):
            raise ValidationError("GPU native invocation failures require an immutable tuple.")
        if not isinstance(self.cancelled, bool):
            raise ValidationError("GPU native invocation cancellation must be explicit boolean.")


@dataclass(frozen=True, slots=True)
class GPUControlReduction:
    changed: bool | None
    unresolved: bool
    requested_verified: bool
    persistence_eligible: bool


@dataclass(frozen=True, slots=True)
class GPUSlotReadResult:
    payload: JSONDict
    state: GPUSlotReadState
    source_format: int | None
    revision: str | None
    migration_required: bool
    recovery_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ] = ()


class GPURecoveryAdmissionState(StrEnum):
    CLEAR = "clear"
    RECOVERY_REQUIRED = "recovery_required"
    IDENTITY_CONFLICT = "identity_conflict"
    STORE_UNAVAILABLE = "store_unavailable"


@dataclass(frozen=True, slots=True)
class GPURecoveryAdmission:
    state: GPURecoveryAdmissionState
    operation_id: str | None


class GPUControlStartupDisposition(StrEnum):
    SKIPPED_POLICY_DISABLED = "skipped_policy_disabled"
    ADMISSION_OBSERVED = "admission_observed"


@dataclass(frozen=True, slots=True)
class GPUControlStartupResult:
    disposition: GPUControlStartupDisposition
    admission: GPURecoveryAdmission | None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, GPUControlStartupDisposition):
            raise ValidationError("GPU startup requires its explicit disposition.")
        if self.disposition == GPUControlStartupDisposition.SKIPPED_POLICY_DISABLED:
            if self.admission is not None:
                raise ValidationError("GPU disabled startup cannot claim observed admission.")
            return
        admission = self.admission
        if not isinstance(admission, GPURecoveryAdmission) or not isinstance(
            admission.state, GPURecoveryAdmissionState
        ):
            raise ValidationError("GPU startup requires actual typed admission.")
        if admission.operation_id is not None:
            require_canonical_trimmed_json_text(
                admission.operation_id, error_message="GPU startup recovery operation is invalid."
            )
        if (
            admission.state
            in (GPURecoveryAdmissionState.CLEAR, GPURecoveryAdmissionState.STORE_UNAVAILABLE)
            and admission.operation_id is not None
        ):
            raise ValidationError("GPU startup admission conflicts with its operation authority.")


@dataclass(frozen=True, slots=True)
class NativeMemberObservation:
    value: int | float | None
    mode: int | str | None
    target_matched: bool

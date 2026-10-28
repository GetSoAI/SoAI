"""SoAI - GPU durable native recovery record contracts [backend/core/hardware/gpu_recovery_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import GPUControlCommitIntent
from core.hardware.gpu_identity_normalization import normalize_observed_full_pci_bdf
from core.hardware.gpu_physical_identity import GPUPhysicalIdentity
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.strict_numbers import require_optional_non_negative_int_strict
from core.validation.strings import require_canonical_trimmed_json_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

    type GPUControlMemberKey = tuple[str, str, str, int | None, int | None]

__all__ = (
    "require_gpu_control_member_keys",
    "GPURecoveryPhase",
    "GPUOriginalObservationState",
    "GPUEffectState",
    "GPUVerificationState",
    "GPURestorationState",
    "GPURecoveryMember",
    "GPURecoveryRecord",
    "GPUStartupLegacyCommit",
    "GPUStartupRecoveryRecord",
    "GPUStartupLegacyRecoveryRecord",
)


class GPURecoveryPhase(StrEnum):
    PREPARED = "prepared"
    RECONCILING = "reconciling"
    UNRESOLVED = "unresolved"


class GPUOriginalObservationState(StrEnum):
    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"


class GPUEffectState(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    ATTEMPTED_UNKNOWN = "attempted_unknown"
    APPLIED = "applied"
    FAILED = "failed"


class GPUVerificationState(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class GPURestorationState(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    RESTORED = "restored"
    MISMATCHED = "mismatched"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class GPURecoveryMember:
    field: str
    member_id: str
    domain_id: int | None
    pstate_id: int | None
    original_value: int | float | None
    original_mode: int | str | None
    native_unit: str
    original_observation: GPUOriginalObservationState
    effect: GPUEffectState
    verification: GPUVerificationState
    restoration: GPURestorationState
    backend: str | None
    changed: bool | None
    requested_value: int | float | None
    requested_mode: int | str | None


@dataclass(frozen=True, slots=True)
class GPURecoveryRecord:
    operation_id: str
    device_id: str
    physical_identity: GPUPhysicalIdentity
    backend: str
    phase: GPURecoveryPhase
    requested_settings: JSONDict
    requested_modes: JSONDict
    requested_units: JSONDict
    members: tuple[GPURecoveryMember, ...]
    pci_bdf_observations: tuple[str, ...] | None
    commit_intent: GPUControlCommitIntent | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.physical_identity, GPUPhysicalIdentity)
            or self.physical_identity.native_device_path is not None
        ):
            raise ValidationError(
                "GPU recovery requires durable UUID, PCI or Windows PNP authority."
            )
        if self.commit_intent is not None and (
            not isinstance(self.commit_intent, GPUControlCommitIntent)
            or not isinstance(self.requested_settings, dict)
            or not set(self.commit_intent.user_fields).issubset(self.requested_settings)
        ):
            raise ValidationError("GPU commit user fields must belong to the complete native plan.")


@dataclass(frozen=True, slots=True)
class GPUStartupLegacyCommit:
    committed_at: str
    completed_control_state_digest: str

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.committed_at, error_message="GPU startup committed timestamp is invalid."
        )
        require_canonical_sha256_hexdigest(
            self.completed_control_state_digest, label="GPU startup completed control digest"
        )


@dataclass(frozen=True, slots=True)
class GPUStartupRecoveryRecord:
    startup_operation_id: str
    device_id: str
    original_record: GPURecoveryRecord
    legacy_record: GPURecoveryRecord
    legacy_commit: GPUStartupLegacyCommit | None

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.startup_operation_id, error_message="GPU startup operation identifier is invalid."
        )
        require_canonical_trimmed_json_text(
            self.device_id, error_message="GPU startup device identifier is invalid."
        )
        if not isinstance(self.original_record, GPURecoveryRecord) or not isinstance(
            self.legacy_record, GPURecoveryRecord
        ):
            raise ValidationError("GPU startup recovery requires two complete plain records.")
        children = (self.original_record, self.legacy_record)
        for child in children:
            require_canonical_trimmed_json_text(
                child.operation_id,
                error_message="GPU startup child operation identifier is invalid.",
            )
            if child.device_id != self.device_id:
                raise ValidationError("GPU startup child device identifiers conflict.")
            if not isinstance(child.physical_identity, GPUPhysicalIdentity):
                raise ValidationError("GPU startup child physical identity is invalid.")
        if (
            len(
                {
                    self.startup_operation_id,
                    self.original_record.operation_id,
                    self.legacy_record.operation_id,
                }
            )
            != 3
        ):
            raise ValidationError("GPU startup child operation identifiers must be distinct.")
        original = self.original_record.physical_identity
        legacy = self.legacy_record.physical_identity
        agreements: list[bool] = []
        if original.uuid is not None and legacy.uuid is not None:
            agreements.append(original.uuid.casefold() == legacy.uuid.casefold())
        if original.pci_bdf_full is not None and legacy.pci_bdf_full is not None:
            agreements.append(
                normalize_observed_full_pci_bdf(original.pci_bdf_full)
                == normalize_observed_full_pci_bdf(legacy.pci_bdf_full)
            )
        if (
            original.windows_pnp_instance_id is not None
            and legacy.windows_pnp_instance_id is not None
        ):
            agreements.append(original.windows_pnp_instance_id == legacy.windows_pnp_instance_id)
        if not agreements or not all(agreements):
            raise ValidationError(
                "GPU startup child physical identity relation is unproved or contradictory."
            )
        identity = GPUPhysicalIdentity(
            original.uuid or legacy.uuid,
            original.pci_bdf_full or legacy.pci_bdf_full,
            windows_pnp_instance_id=original.windows_pnp_instance_id
            or legacy.windows_pnp_instance_id,
        )
        observations: list[str] = []
        member_keys: list[set[GPUControlMemberKey]] = []
        for child in children:
            if child.pci_bdf_observations is not None:
                child.physical_identity.validate_observations(child.pci_bdf_observations)
                observations.extend(child.pci_bdf_observations)
            if not isinstance(child.members, tuple) or not child.members:
                raise ValidationError("GPU startup child requires immutable native members.")
            keys: set[GPUControlMemberKey] = set()
            for member in child.members:
                if not isinstance(member, GPURecoveryMember) or member.backend is None:
                    raise ValidationError("GPU startup child member routing is unrecorded.")
                key = (
                    member.backend,
                    member.field,
                    member.member_id,
                    member.domain_id,
                    member.pstate_id,
                )
                if key in keys:
                    raise ValidationError("GPU startup child contains duplicate native members.")
                keys.add(key)
            member_keys.append(keys)
        identity.validate_observations(tuple(observations))
        if member_keys[0] & member_keys[1]:
            raise ValidationError("GPU startup original and legacy native member scopes overlap.")
        if self.legacy_record.commit_intent is None or any(
            member.requested_value is None and member.requested_mode is None
            for member in self.legacy_record.members
        ):
            raise ValidationError(
                "GPU startup legacy record requires frozen targets and commit intent."
            )
        if self.legacy_commit is not None and not isinstance(
            self.legacy_commit, GPUStartupLegacyCommit
        ):
            raise ValidationError("GPU startup legacy commit is invalid.")


@dataclass(frozen=True, slots=True)
class GPUStartupLegacyRecoveryRecord:
    startup_operation_id: str
    device_id: str
    legacy_record: GPURecoveryRecord
    legacy_commit: GPUStartupLegacyCommit | None

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.startup_operation_id, error_message="GPU startup operation identifier is invalid."
        )
        require_canonical_trimmed_json_text(
            self.device_id, error_message="GPU startup device identifier is invalid."
        )
        child = self.legacy_record
        if not isinstance(child, GPURecoveryRecord):
            raise ValidationError("GPU startup legacy recovery requires a complete plain record.")
        require_canonical_trimmed_json_text(
            child.operation_id, error_message="GPU startup child operation identifier is invalid."
        )
        if child.device_id != self.device_id or child.operation_id == self.startup_operation_id:
            raise ValidationError("GPU startup legacy device or operation identifiers conflict.")
        if not isinstance(child.physical_identity, GPUPhysicalIdentity):
            raise ValidationError("GPU startup legacy physical identity is invalid.")
        if child.pci_bdf_observations is not None:
            child.physical_identity.validate_observations(child.pci_bdf_observations)
        if not isinstance(child.members, tuple) or not child.members:
            raise ValidationError("GPU startup legacy requires immutable native members.")
        keys: set[GPUControlMemberKey] = set()
        for member in child.members:
            if not isinstance(member, GPURecoveryMember) or member.backend is None:
                raise ValidationError("GPU startup legacy member routing is unrecorded.")
            key = (
                member.backend,
                member.field,
                member.member_id,
                member.domain_id,
                member.pstate_id,
            )
            if key in keys:
                raise ValidationError("GPU startup legacy contains duplicate native members.")
            keys.add(key)
            if member.requested_value is None and member.requested_mode is None:
                raise ValidationError("GPU startup legacy requires frozen native targets.")
        if child.commit_intent is None:
            raise ValidationError("GPU startup legacy requires complete commit intent.")
        if self.legacy_commit is not None and not isinstance(
            self.legacy_commit, GPUStartupLegacyCommit
        ):
            raise ValidationError("GPU startup legacy commit is invalid.")


def require_gpu_control_member_keys(keys: tuple[GPUControlMemberKey, ...]) -> None:
    if not isinstance(keys, tuple):
        raise ValidationError("GPU startup native member keys require an immutable tuple.")
    for key in keys:
        if not isinstance(key, tuple) or len(key) != 5:
            raise ValidationError("GPU startup native member key is invalid.")
        for value in key[:3]:
            require_canonical_trimmed_json_text(
                value, error_message="GPU startup native member identity is invalid."
            )
        require_optional_non_negative_int_strict(
            key[3], error_message="GPU startup native domain is invalid."
        )
        require_optional_non_negative_int_strict(
            key[4], error_message="GPU startup native Pstate is invalid."
        )
    if len(set(keys)) != len(keys):
        raise ValidationError("GPU startup native member keys are duplicated.")

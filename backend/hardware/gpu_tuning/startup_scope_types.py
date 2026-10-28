"""SoAI - Immutable native startup accounting and footprint types [backend/hardware/gpu_tuning/startup_scope_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
from core.hardware.gpu_control_types import GPUControlResult, GPUPreparedControl
from core.hardware.gpu_physical_identity import (
    GPUInventoryReadState,
    GPUPhysicalBindingState,
    GPUPhysicalDevice,
    GPUPhysicalSnapshot,
)
from core.hardware.gpu_recovery_records import (
    GPUOriginalObservationState,
    GPURecoveryRecord,
    GPUStartupLegacyCommit,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
    require_gpu_control_member_keys,
)
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.strings import require_canonical_trimmed_json_text

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import GPUControlMemberKey

__all__ = (
    "GPUStartupScopePolicy",
    "GPUStartupRecordedGoal",
    "GPUStartupRecordedScope",
    "GPUStartupFacilityScope",
    "GPULegacyResetRoster",
    "GPULegacyResetDevicePlan",
    "GPUControlLegacyResetPlan",
    "GPUControlStartupScope",
    "GPUStartupActuatorFootprint",
    "GPUStartupPromotionProof",
    "GPUStartupScopeReadback",
    "GPUControlStartupVerification",
)


class GPUStartupScopePolicy(StrEnum):
    RECORDED_RECOVERY = "recorded_recovery"
    HISTORICAL_WHOLE_POOL = "historical_whole_pool"


class GPUStartupRecordedGoal(StrEnum):
    ORIGINAL = "original"
    UNCOMMITTED_LEGACY = "uncommitted_legacy"
    COMMITTED_LEGACY_TARGET = "committed_legacy_target"


@dataclass(frozen=True, slots=True)
class GPUStartupRecordedScope:
    record: GPURecoveryRecord
    goal: GPUStartupRecordedGoal
    target: GPUPhysicalDevice | None
    legacy_commit: GPUStartupLegacyCommit | None
    state: GPUPhysicalBindingState
    reason_code: str | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.record, GPURecoveryRecord)
            or not isinstance(self.goal, GPUStartupRecordedGoal)
            or not isinstance(self.state, GPUPhysicalBindingState)
        ):
            raise ValidationError("GPU startup recorded scope is invalid.")
        if self.target is not None and (
            not isinstance(self.target, GPUPhysicalDevice)
            or self.target.device_id != self.record.device_id
        ):
            raise ValidationError("GPU startup recorded target conflicts with the original scope.")
        if self.state == GPUPhysicalBindingState.BOUND and self.target is None:
            raise ValidationError("GPU startup bound scope requires its actual target.")
        if self.goal == GPUStartupRecordedGoal.COMMITTED_LEGACY_TARGET:
            if not isinstance(self.legacy_commit, GPUStartupLegacyCommit):
                raise ValidationError(
                    "GPU startup committed legacy goal requires its durable commit."
                )
        elif self.legacy_commit is not None:
            raise ValidationError("GPU startup noncommitted goal cannot carry a legacy commit.")


@dataclass(frozen=True, slots=True)
class GPUStartupFacilityScope:
    target: GPUPhysicalDevice
    backend: str
    field: str
    member_keys: tuple[GPUControlMemberKey, ...]
    state: GPUOriginalObservationState
    reason_code: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.target, GPUPhysicalDevice) or not isinstance(
            self.state, GPUOriginalObservationState
        ):
            raise ValidationError("GPU startup facility scope is invalid.")
        require_canonical_trimmed_json_text(
            self.backend, error_message="GPU startup facility backend is invalid."
        )
        require_canonical_trimmed_json_text(
            self.field, error_message="GPU startup facility field is invalid."
        )
        require_gpu_control_member_keys(self.member_keys)
        if any(key[0] != self.backend or key[1] != self.field for key in self.member_keys):
            raise ValidationError("GPU startup facility member routing is contradictory.")
        if self.state == GPUOriginalObservationState.OBSERVED and not self.member_keys:
            raise ValidationError("GPU startup observed facility requires actual native members.")
        if self.state == GPUOriginalObservationState.UNSUPPORTED and self.member_keys:
            raise ValidationError("GPU startup unsupported facility cannot claim native members.")


@dataclass(frozen=True, slots=True)
class GPULegacyResetRoster:
    vendor: str
    backend: str
    acquisition_id: str
    state: GPUInventoryReadState
    devices: tuple[GPUPhysicalDevice, ...]
    reason_code: str | None

    def __post_init__(self) -> None:
        require_canonical_trimmed_json_text(
            self.vendor, error_message="GPU startup roster vendor is invalid."
        )
        require_canonical_trimmed_json_text(
            self.backend, error_message="GPU startup roster backend is invalid."
        )
        require_canonical_trimmed_json_text(
            self.acquisition_id, error_message="GPU startup roster acquisition is invalid."
        )
        if (
            not isinstance(self.state, GPUInventoryReadState)
            or not isinstance(self.devices, tuple)
            or any(
                not isinstance(device, GPUPhysicalDevice) or device.vendor != self.vendor
                for device in self.devices
            )
        ):
            raise ValidationError("GPU startup native roster is invalid.")


@dataclass(frozen=True, slots=True)
class GPULegacyResetDevicePlan:
    target: GPUPhysicalDevice
    facilities: tuple[GPUStartupFacilityScope, ...]
    record: GPURecoveryRecord | None
    rejection: GPUControlPreflightRejection | None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target, GPUPhysicalDevice)
            or not isinstance(self.facilities, tuple)
            or any(
                not isinstance(facility, GPUStartupFacilityScope) or facility.target != self.target
                for facility in self.facilities
            )
        ):
            raise ValidationError("GPU startup device facility accounting is invalid.")
        if self.record is not None and (
            not isinstance(self.record, GPURecoveryRecord)
            or self.record.device_id != self.target.device_id
        ):
            raise ValidationError("GPU startup legacy record target is contradictory.")
        if self.rejection is not None and not isinstance(
            self.rejection, GPUControlPreflightRejection
        ):
            raise ValidationError("GPU startup legacy rejection is invalid.")


@dataclass(frozen=True, slots=True)
class GPUControlLegacyResetPlan:
    physical_snapshot: GPUPhysicalSnapshot
    rosters: tuple[GPULegacyResetRoster, ...]
    devices: tuple[GPULegacyResetDevicePlan, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.physical_snapshot, GPUPhysicalSnapshot)
            or not isinstance(self.rosters, tuple)
            or any(not isinstance(roster, GPULegacyResetRoster) for roster in self.rosters)
            or not isinstance(self.devices, tuple)
            or any(not isinstance(device, GPULegacyResetDevicePlan) for device in self.devices)
        ):
            raise ValidationError("GPU startup legacy reset plan is invalid.")


@dataclass(frozen=True, slots=True)
class GPUControlStartupScope:
    policy: GPUStartupScopePolicy
    physical_snapshot: GPUPhysicalSnapshot
    initial_records: tuple[
        GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...
    ]
    recorded: tuple[GPUStartupRecordedScope, ...]
    legacy_plan: GPUControlLegacyResetPlan | None

    def __post_init__(self) -> None:
        if not isinstance(self.policy, GPUStartupScopePolicy) or not isinstance(
            self.physical_snapshot, GPUPhysicalSnapshot
        ):
            raise ValidationError("GPU startup scope policy or physical snapshot is invalid.")
        if (
            not isinstance(self.initial_records, tuple)
            or any(
                not isinstance(
                    record,
                    GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord,
                )
                for record in self.initial_records
            )
            or not isinstance(self.recorded, tuple)
            or any(not isinstance(record, GPUStartupRecordedScope) for record in self.recorded)
        ):
            raise ValidationError(
                "GPU startup scope requires immutable complete record accounting."
            )
        if self.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
            if (
                not isinstance(self.legacy_plan, GPUControlLegacyResetPlan)
                or self.legacy_plan.physical_snapshot != self.physical_snapshot
            ):
                raise ValidationError(
                    "GPU startup historical scope requires the exact legacy physical snapshot."
                )
        elif self.legacy_plan is not None:
            raise ValidationError(
                "GPU startup recorded recovery cannot introduce speculative legacy scope."
            )


@dataclass(frozen=True, slots=True)
class GPUStartupActuatorFootprint:
    target: GPUPhysicalDevice
    backend: str
    actuator_name: str
    native_member_keys: tuple[GPUControlMemberKey, ...]
    affected_fields: tuple[str, ...]
    setup_member_keys: tuple[GPUControlMemberKey, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.target, GPUPhysicalDevice):
            raise ValidationError("GPU startup actuator footprint target is invalid.")
        require_canonical_trimmed_json_text(
            self.backend, error_message="GPU startup actuator backend is invalid."
        )
        require_canonical_trimmed_json_text(
            self.actuator_name, error_message="GPU startup actuator name is invalid."
        )
        require_gpu_control_member_keys(self.native_member_keys)
        require_gpu_control_member_keys(self.setup_member_keys)
        if not self.native_member_keys or not set(self.setup_member_keys).issubset(
            self.native_member_keys
        ):
            raise ValidationError(
                "GPU startup actuator footprint requires complete setup/member coverage."
            )
        if any(key[0] != self.backend for key in self.native_member_keys):
            raise ValidationError("GPU startup actuator backend/member routing conflicts.")
        if (
            not isinstance(self.affected_fields, tuple)
            or not self.affected_fields
            or len(set(self.affected_fields)) != len(self.affected_fields)
        ):
            raise ValidationError(
                "GPU startup actuator fields require an immutable distinct tuple."
            )
        for field in self.affected_fields:
            require_canonical_trimmed_json_text(
                field, error_message="GPU startup actuator affected field is invalid."
            )
        if not {key[1] for key in self.native_member_keys}.issubset(self.affected_fields):
            raise ValidationError("GPU startup actuator footprint omits a touched member field.")


@dataclass(frozen=True, slots=True)
class GPUStartupPromotionProof:
    target: GPUPhysicalDevice
    original_scope_digest: str
    legacy_scope_digest: str
    acquisition_id: str
    actuators: tuple[GPUStartupActuatorFootprint, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.target, GPUPhysicalDevice)
            or not isinstance(self.actuators, tuple)
            or any(
                not isinstance(actuator, GPUStartupActuatorFootprint)
                or actuator.target != self.target
                for actuator in self.actuators
            )
        ):
            raise ValidationError("GPU startup promotion footprint is invalid.")
        require_canonical_sha256_hexdigest(
            self.original_scope_digest, label="GPU startup original scope digest"
        )
        require_canonical_sha256_hexdigest(
            self.legacy_scope_digest, label="GPU startup legacy scope digest"
        )
        require_canonical_trimmed_json_text(
            self.acquisition_id, error_message="GPU startup promotion acquisition is invalid."
        )


@dataclass(frozen=True, slots=True)
class GPUStartupScopeReadback:
    record: GPURecoveryRecord
    goal: GPUStartupRecordedGoal
    result: GPUControlResult
    prepared: GPUPreparedControl


@dataclass(frozen=True, slots=True)
class GPUControlStartupVerification:
    scope: GPUControlStartupScope
    physical_snapshot: GPUPhysicalSnapshot
    rosters: tuple[GPULegacyResetRoster, ...]
    recorded_readbacks: tuple[GPUStartupScopeReadback, ...]
    legacy_readbacks: tuple[GPUStartupScopeReadback, ...]
    facilities: tuple[GPUStartupFacilityScope, ...]

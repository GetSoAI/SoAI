"""SoAI - Durable GPU preparation, checkpoints and atomic completion [backend/hardware/gpu_tuning/native_control_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_types import (
    GPUPreparedControl,
    GPURecoveryAdmission,
    GPURecoveryAdmissionState,
    GPUSlotReadError,
)
from core.hardware.gpu_recovery_records import (
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from hardware.gpu_tuning.control_recovery_checkpoints import (
    create_prepared_recovery,
    create_startup_legacy_recovery,
    persist_pending_effect_checkpoint,
    persist_recovery_checkpoint,
    resume_original_recovery_checkpoint,
    resume_startup_recorded_goal,
)
from hardware.gpu_tuning.control_recovery_completion import (
    GPURecoveryPendingCommit,
    complete_original_recovery,
    complete_requested_recovery,
    inspect_recovery_admission,
)
from hardware.gpu_tuning.control_recovery_records import (
    require_current_recovery_record,
    require_native_result_record,
    require_plain_recovery_record,
    require_startup_member_authority,
    require_uncommitted_startup_effect,
    validate_prepared_record,
)
from hardware.gpu_tuning.control_recovery_startup_scope import GPURecoveryStartupScope
from hardware.gpu_tuning.dirty_shutdown_flag import (
    require_gpu_marker_store_read,
)
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.startup_reconciliation_authority import promote_startup_recovery
from hardware.gpu_tuning.startup_scope_types import GPUStartupRecordedGoal, GPUStartupScopePolicy

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import (
        GPUControlCommitAcknowledgement,
        GPUControlResult,
        GPUSlotReadResult,
    )
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.hardware.gpu_recovery_records import GPUControlMemberKey, GPURecoveryRecord
    from hardware.gpu_tuning.service_dependencies import GPUStartupAcquisitionResources
    from hardware.gpu_tuning.startup_scope_types import GPUStartupPromotionProof

__all__ = ("NativeControlRecovery", "NativeControlRecoveryDependencies")


@dataclass(frozen=True, slots=True)
class NativeControlRecoveryDependencies:
    storage: GpuSlotStorageManagerProtocol
    dirty_flag_path: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="NativeControlRecoveryDependencies",
            storage=self.storage,
            dirty_flag_path=self.dirty_flag_path,
        )


class NativeControlRecovery:
    def __init__(self, dependencies: NativeControlRecoveryDependencies) -> None:
        self.dependencies = dependencies
        self._pending_durability: dict[str, GPURecoveryPendingCommit] = {}
        self.startup_scope = GPURecoveryStartupScope(
            dependencies.storage,
            dependencies.dirty_flag_path,
            self._pending_durability,
            dependencies.storage.lock,
        )

    def inspect(self, target: GPUPhysicalDevice) -> GPURecoveryAdmission:
        try:
            with self.dependencies.storage.lock:
                read = self.dependencies.storage.read_payload()
                self._require_available_state(read)
                admission = inspect_recovery_admission(target, read, self._pending_durability)
                if (
                    admission.state == GPURecoveryAdmissionState.CLEAR
                    and self.startup_scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL
                ):
                    return GPURecoveryAdmission(GPURecoveryAdmissionState.RECOVERY_REQUIRED, None)
                return admission
        except GPUSlotReadError:
            return GPURecoveryAdmission(GPURecoveryAdmissionState.STORE_UNAVAILABLE, None)

    def startup_admission(self) -> GPURecoveryAdmission:
        try:
            with self.dependencies.storage.lock:
                read = self.dependencies.storage.read_payload()
                self._require_available_state(read)
                if self._pending_durability or read.recovery_records:
                    record = (
                        next(iter(self._pending_durability.values())).record
                        if self._pending_durability
                        else read.recovery_records[0]
                    )
                    operation_id = (
                        record.startup_operation_id
                        if isinstance(
                            record, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord
                        )
                        else record.operation_id
                    )
                    return GPURecoveryAdmission(
                        GPURecoveryAdmissionState.RECOVERY_REQUIRED, operation_id
                    )
                if self.startup_scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
                    return GPURecoveryAdmission(GPURecoveryAdmissionState.RECOVERY_REQUIRED, None)
                return GPURecoveryAdmission(GPURecoveryAdmissionState.CLEAR, None)
        except GPUSlotReadError:
            return GPURecoveryAdmission(GPURecoveryAdmissionState.STORE_UNAVAILABLE, None)

    def prepare(self, target: GPUPhysicalDevice, record: GPURecoveryRecord) -> GPUPreparedControl:
        record = copy.deepcopy(record)
        validate_prepared_record(record, target)
        storage = self.dependencies.storage
        with storage.lock:
            read = storage.read_payload()
            self._require_available_state(read)
            if self.startup_scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
                raise ValidationError("GPU historical recovery blocks new mutation.")
            return create_prepared_recovery(storage, self._pending_durability, target, record)

    def prepare_startup_legacy(
        self, target: GPUPhysicalDevice, record: GPURecoveryRecord, *, startup_operation_id: str
    ) -> GPUPreparedControl:
        with self.dependencies.storage.lock:
            if self.startup_scope.active_scope is None:
                raise ValidationError("GPU legacy preparation requires its bound startup owner.")
            return create_startup_legacy_recovery(
                self.dependencies.storage,
                self._pending_durability,
                self.startup_scope.active_scope,
                target,
                record,
                startup_operation_id,
            )

    def promote_startup(
        self,
        target: GPUPhysicalDevice,
        *,
        record: GPUStartupRecoveryRecord,
        expected_read: GPUSlotReadResult,
        proof: GPUStartupPromotionProof,
        resources: GPUStartupAcquisitionResources,
    ) -> GPUPreparedControl:
        with self.dependencies.storage.lock:
            scope = self.startup_scope.active_scope
            if scope is None:
                raise ValidationError("GPU promotion requires its actual bound startup lifetime.")
            return promote_startup_recovery(
                self.dependencies.storage,
                pending=self._pending_durability,
                scope=scope,
                target=target,
                record=record,
                expected_read=expected_read,
                proof=proof,
                resources=resources,
            )

    def resume_startup_recorded(
        self, target: GPUPhysicalDevice, *, operation_id: str, goal: GPUStartupRecordedGoal
    ) -> GPUPreparedControl:
        with self.dependencies.storage.lock:
            scope = self.startup_scope.active_scope
            if scope is None or target.device_id in self._pending_durability:
                raise ValidationError("GPU recorded startup goal requires its bound durable owner.")
            return resume_startup_recorded_goal(
                self.dependencies.storage, scope, target, operation_id, goal
            )

    def resume_reconciliation(self, target: GPUPhysicalDevice) -> GPUPreparedControl:
        return resume_original_recovery_checkpoint(self.dependencies.storage, target)

    def before_effect(
        self, prepared: GPUPreparedControl, member_key: GPUControlMemberKey
    ) -> GPUPreparedControl:
        storage = self.dependencies.storage
        with storage.lock:
            read, record = self._current(prepared)
            if member_key not in prepared.member_keys:
                raise ValidationError("GPU effect is outside prepared member authority.")
            require_uncommitted_startup_effect(read, prepared)
            if self.startup_scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL or any(
                isinstance(stored, GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord)
                and stored.device_id == prepared.target.device_id
                for stored in read.recovery_records
            ):
                require_startup_member_authority(
                    self.startup_scope.active_scope, record, prepared, member_key
                )
            prepared = self.startup_scope.establish_marker(prepared)
            return persist_pending_effect_checkpoint(storage, prepared, read, record, member_key)

    def record_result(
        self, prepared: GPUPreparedControl, result: GPUControlResult
    ) -> GPUPreparedControl:
        reduction = reduce_gpu_control_result(result, prepared=prepared)
        storage = self.dependencies.storage
        with storage.lock:
            read, record = self._current(prepared)
            updated = require_native_result_record(record, prepared, result, reduction)
            return persist_recovery_checkpoint(storage, prepared, read, updated)

    def finish(
        self, prepared: GPUPreparedControl, result: GPUControlResult
    ) -> GPUControlCommitAcknowledgement | None:
        storage = self.dependencies.storage
        with storage.lock:
            read, record = self._current(prepared)
            require_plain_recovery_record(read, prepared.target.device_id)
            if self.startup_scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
                raise StateError("GPU historical marker requires whole-scope recovery completion.")
            reduction = reduce_gpu_control_result(result, prepared=prepared)
            if (
                reduction.changed is not False
                or reduction.unresolved
                or self.startup_scope.live_receipt is not None
            ):
                prepared = self.startup_scope.establish_marker(prepared)
            return complete_requested_recovery(
                storage, self._pending_durability, prepared, read, record, result
            )

    def finish_reconciliation(self, prepared: GPUPreparedControl, result: GPUControlResult) -> None:
        storage = self.dependencies.storage
        with storage.lock:
            read, record = self._current(prepared)
            require_plain_recovery_record(read, prepared.target.device_id)
            if self.startup_scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL:
                raise StateError("GPU historical marker requires whole-scope recovery completion.")
            reduction = reduce_gpu_control_result(result, prepared=prepared)
            if (
                reduction.changed is not False
                or reduction.unresolved
                or self.startup_scope.live_receipt is not None
            ):
                prepared = self.startup_scope.establish_marker(prepared)
            complete_original_recovery(
                storage, self._pending_durability, prepared, read, record, result
            )

    def require_clean_shutdown(self) -> None:
        with self.dependencies.storage.lock:
            read = self.dependencies.storage.read_payload()
            self._require_available_state(read)
            if (
                self.startup_scope.policy == GPUStartupScopePolicy.HISTORICAL_WHOLE_POOL
                or read.recovery_records
                or self._pending_durability
            ):
                raise StateError("GPU unresolved recovery prevents clean shutdown.")

    def _require_available_state(self, read: GPUSlotReadResult) -> None:
        require_gpu_marker_store_read(
            read,
            marker_path=self.dependencies.dirty_flag_path,
            pending_devices=tuple(self._pending_durability),
        )

    def _current(self, prepared: GPUPreparedControl) -> tuple[GPUSlotReadResult, GPURecoveryRecord]:
        read = self.dependencies.storage.read_payload()
        return read, require_current_recovery_record(read, prepared)

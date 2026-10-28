"""SoAI - Owned startup scope lifetime and dirty marker authority [backend/hardware/gpu_tuning/control_recovery_startup_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from threading import RLock
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_types import GPUSlotReadError
from hardware.gpu_tuning.dirty_shutdown_flag import (
    establish_gpu_dirty_marker_receipt,
    observe_gpu_startup_marker_policy,
)
from hardware.gpu_tuning.startup_recovery_completion import (
    complete_startup_recovery,
    reconcile_startup_recovery,
)
from hardware.gpu_tuning.startup_scope_accounting import require_complete_startup_accounting
from hardware.gpu_tuning.startup_scope_types import GPUStartupScopePolicy

if TYPE_CHECKING:
    from core.hardware.gpu_control_types import (
        GPUControlDirtyMarkerReceipt,
        GPUPreparedControl,
        GPUSlotReadResult,
    )
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from hardware.gpu_tuning.control_recovery_completion import GPURecoveryPendingCommit
    from hardware.gpu_tuning.startup_scope_types import (
        GPUControlStartupScope,
        GPUControlStartupVerification,
    )


__all__ = ("GPURecoveryStartupScope",)


@dataclass(slots=True)
class GPURecoveryStartupScope:
    storage: GpuSlotStorageManagerProtocol
    marker_path: str
    pending: dict[str, GPURecoveryPendingCommit]
    storage_lock: RLock
    _live_receipt: GPUControlDirtyMarkerReceipt | None = field(init=False, default=None)
    _active_scope: GPUControlStartupScope | None = field(init=False, default=None)
    _policy: GPUStartupScopePolicy | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.storage_lock is not self.storage.lock:
            raise ValidationError("GPU startup scope must share its actual storage lock.")
        try:
            self._policy = observe_gpu_startup_marker_policy(self.marker_path, None, None)
        except GPUSlotReadError:
            self._policy = None

    @property
    def policy(self) -> GPUStartupScopePolicy:
        with self.storage_lock:
            self._policy = observe_gpu_startup_marker_policy(
                self.marker_path, self._policy, self._live_receipt
            )
            return self._policy

    @property
    def live_receipt(self) -> GPUControlDirtyMarkerReceipt | None:
        return self._live_receipt

    @property
    def active_scope(self) -> GPUControlStartupScope | None:
        with self.storage_lock:
            return copy.deepcopy(self._active_scope)

    def bind(self, scope: GPUControlStartupScope) -> None:
        with self.storage_lock:
            owned = copy.deepcopy(scope)
            require_complete_startup_accounting(owned)
            if self.pending or self._active_scope is not None or owned.policy != self.policy:
                raise ValidationError("GPU startup scope conflicts with its marker owner.")
            if self.storage.read_payload().recovery_records != owned.initial_records:
                raise ValidationError("GPU startup initial durable scope changed.")
            self._active_scope = owned

    def release(self, scope: GPUControlStartupScope) -> None:
        with self.storage_lock:
            if self._active_scope != scope:
                raise ValidationError("GPU startup scope release belongs to another operation.")
            self._active_scope = None

    def establish_marker(self, prepared: GPUPreparedControl) -> GPUPreparedControl:
        with self.storage_lock:
            self._live_receipt = None
            self._live_receipt = establish_gpu_dirty_marker_receipt(
                self.marker_path, prepared.dirty_marker_receipt
            )
            return replace(prepared, dirty_marker_receipt=self._live_receipt)

    def finish(
        self, initial_read: GPUSlotReadResult, verification: GPUControlStartupVerification
    ) -> GPUSlotReadResult:
        with self.storage_lock:
            if self._active_scope != verification.scope:
                raise ValidationError("GPU aggregate completion requires its bound startup scope.")
            read = complete_startup_recovery(
                self.storage,
                pending=self.pending,
                initial_read=initial_read,
                verification=verification,
                dirty_flag_path=self.marker_path,
            )
            self._policy = observe_gpu_startup_marker_policy(
                self.marker_path, GPUStartupScopePolicy.RECORDED_RECOVERY, None
            )
            self._live_receipt = None
            return read

    def repair(self, verification: GPUControlStartupVerification) -> GPUSlotReadResult:
        with self.storage_lock:
            if self._active_scope is not None and self._active_scope != verification.scope:
                raise ValidationError("GPU aggregate repair requires its bound startup scope.")
            read = reconcile_startup_recovery(
                self.storage, pending=self.pending, verification=verification
            )
            self._policy = observe_gpu_startup_marker_policy(
                self.marker_path, GPUStartupScopePolicy.RECORDED_RECOVERY, None
            )
            self._live_receipt = None
            return read

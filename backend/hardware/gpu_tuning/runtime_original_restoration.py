"""SoAI - Runtime restoration of unresolved recorded GPU originals [backend/hardware/gpu_tuning/runtime_original_restoration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.hardware.gpu_control_types import (
    GPUControlReduction,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.hardware.gpu_operation_results import build_gpu_result
from hardware.gpu_tuning.control_recovery_records import require_current_recovery_record
from hardware.gpu_tuning.control_worker_results import (
    GPU_CONTROL_WORKER_EXCEPTIONS,
    GPUControlOperationOutcome,
)
from hardware.gpu_tuning.native_control_results import reduce_gpu_control_result
from hardware.gpu_tuning.vendor_backend_apply import restore_vendor_backend_originals

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_control_types import GPUControlResult, GPUPreparedControl
    from core.hardware.gpu_physical_identity import GPUPhysicalDevice
    from core.types.json import JSONDict
    from hardware.gpu_tuning.dependencies import GpuSettingsApplyDependencies

__all__ = (
    "GPUOriginalRestoration",
    "GPUOriginalRestorationState",
    "reconciled_recovery_outcome",
    "restore_recorded_originals",
)

_OPERATION = "hardware.gpu_tuning.runtime_original_restoration"


class GPUOriginalRestorationState(StrEnum):
    RESTORED = "restored"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class GPUOriginalRestoration:
    state: GPUOriginalRestorationState
    result: GPUControlResult | None
    prepared: GPUPreparedControl | None
    persistence_uncertain: bool

    @property
    def reductions(self) -> tuple[GPUControlReduction, ...]:
        if self.result is not None and self.prepared is not None:
            return (reduce_gpu_control_result(self.result, prepared=self.prepared),)
        if self.state == GPUOriginalRestorationState.UNRESOLVED:
            return (GPUControlReduction(None, True, False, False),)
        return ()


def restore_recorded_originals(
    deps: GpuSettingsApplyDependencies,
    target: GPUPhysicalDevice,
    cancellation_token: CancellationTokenProtocol,
) -> GPUOriginalRestoration:
    recovery = deps.native_control_recovery
    result: GPUControlResult | None = None
    prepared: GPUPreparedControl | None = None
    try:
        prepared = recovery.resume_reconciliation(target)
        with deps.storage.lock:
            record = require_current_recovery_record(deps.storage.read_payload(), prepared)
        result, prepared = restore_vendor_backend_originals(
            executor=deps.executor,
            logger=deps.logger,
            nvidia_settings_controller=deps.nvidia_settings_controller,
            gpu_services=deps.gpu_services,
            target=target,
            record=record,
            prepared=prepared,
            recovery=recovery,
            cancellation_token=cancellation_token,
        )
        recovery.finish_reconciliation(prepared, result)
    except GPUSlotWriteError as slot_exception:
        return _unresolved(
            deps,
            target,
            slot_exception,
            result,
            prepared,
            slot_exception.reason == GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN,
        )
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        return _unresolved(deps, target, exception, result, prepared, False)
    return GPUOriginalRestoration(GPUOriginalRestorationState.RESTORED, result, prepared, False)


def _unresolved(
    deps: GpuSettingsApplyDependencies,
    target: GPUPhysicalDevice,
    exception: Exception,
    result: GPUControlResult | None,
    prepared: GPUPreparedControl | None,
    persistence_uncertain: bool,
) -> GPUOriginalRestoration:
    log_exception(
        deps.logger,
        exception,
        message="GPU recorded originals remain unresolved after restoration.",
        operation=_OPERATION,
        details={"device_id": target.device_id},
        level="warning",
    )
    return GPUOriginalRestoration(
        GPUOriginalRestorationState.UNRESOLVED, result, prepared, persistence_uncertain
    )


def reconciled_recovery_outcome(
    result_key: str, restoration: GPUOriginalRestoration
) -> GPUControlOperationOutcome:
    restored = restoration.state == GPUOriginalRestorationState.RESTORED
    reductions = restoration.reductions
    changed = (
        None
        if restoration.result is None
        else any(reduction.changed is not False for reduction in reductions)
    )
    payload: JSONDict = {
        "success": False,
        "code": "recovery_reconciled" if restored else "recovery_unresolved",
        "original_restoration": restoration.state.value,
        "gpus": {
            result_key: build_gpu_result(
                errors=[
                    (
                        "Previous GPU settings were restored; apply the new settings again."
                        if restored
                        else "Previous GPU settings could not be restored safely."
                    )
                ],
                changed=changed,
            )
        },
    }
    if changed is not None:
        payload["changed"] = changed
    return GPUControlOperationOutcome(
        payload,
        reductions,
        False,
        restoration.persistence_uncertain,
        None,
        False,
        () if restoration.result is None else (restoration.result,),
        (),
        (),
        None if restoration.prepared is None else restoration.prepared.dirty_marker_receipt,
        None,
    )

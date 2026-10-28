"""SoAI - GPU effects finalization and retained worker reduction [backend/hardware/gpu_tuning/control_operation_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.hardware.gpu_control_operation_types import GPUControlCommitIntent
from core.hardware.gpu_control_types import (
    GPUControlReduction,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState, GPUPhysicalDevice
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.validation.strings import require_canonical_trimmed_json_text
from hardware.gpu_inventory.physical_binding import match_gpu_physical_identity
from hardware.gpu_tuning.control_recovery_admission import require_distinct_control_targets
from hardware.gpu_tuning.control_worker_results import (
    GPU_CONTROL_WORKER_EXCEPTIONS,
    GPUControlOperationOutcome,
    failed_gpu_control_payload,
)
from hardware.gpu_tuning.dirty_shutdown_flag import establish_gpu_dirty_marker_receipt
from hardware.gpu_tuning.mutation_leases import GPUControlMetadataScope
from hardware.gpu_tuning.startup_scope_accounting import startup_cleanup_targets
from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies


__all__ = (
    "GPUControlFinalizationTarget",
    "GPUControlSnapshotScope",
    "resolve_gpu_control_operation_scope",
    "GPUControlFinalizationDependencies",
    "finalize_gpu_control_effects",
    "execute_finalized_gpu_control_worker",
)


@dataclass(frozen=True, slots=True)
class GPUControlFinalizationTarget:
    target: GPUPhysicalDevice
    commit_intent: GPUControlCommitIntent
    result_key: str
    scope_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.target, GPUPhysicalDevice) or not isinstance(
            self.commit_intent, GPUControlCommitIntent
        ):
            raise ValidationError("GPU finalization requires frozen target and user intent.")
        require_canonical_trimmed_json_text(
            self.result_key, error_message="GPU result key is invalid."
        )
        require_canonical_sha256_hexdigest(self.scope_digest, label="GPU finalization scope")


@dataclass(frozen=True, slots=True)
class GPUControlSnapshotScope:
    target: GPUPhysicalDevice
    result_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.target, GPUPhysicalDevice):
            raise ValidationError("GPU snapshot control requires an actual physical target.")
        require_canonical_trimmed_json_text(
            self.result_key, error_message="GPU snapshot result key is invalid."
        )

    def require_target(self, actual: GPUPhysicalDevice) -> None:
        entries: list[JSONDict] = [
            {
                "uuid": target.identity.uuid,
                "pci_bdf_full": target.identity.pci_bdf_full,
                "pci_bdf_observations": list(target.pci_bdf_observations),
                "native_device_path": target.identity.native_device_path,
                "windows_pnp_instance_id": target.identity.windows_pnp_instance_id,
            }
            for target in (self.target, actual)
        ]
        if (
            self.target.device_id != actual.device_id
            or self.target.vendor != actual.vendor
            or match_gpu_physical_identity(entries[0], entries[1]) != GPUPhysicalBindingState.BOUND
        ):
            raise ValidationError("GPU snapshot control changed its admitted physical target.")


def resolve_gpu_control_operation_scope(
    targets: (
        tuple[GPUPhysicalDevice, ...]
        | GPUControlStartupScope
        | GPUControlMetadataScope
        | GPUControlSnapshotScope
    ),
) -> tuple[tuple[str, ...], GPUControlStartupScope | GPUControlMetadataScope | None]:
    scope: GPUControlStartupScope | GPUControlMetadataScope | None = None
    if isinstance(targets, GPUControlStartupScope):
        scope = copy.deepcopy(targets)
        targets = startup_cleanup_targets(scope)
        if targets:
            require_distinct_control_targets(targets)
    elif isinstance(targets, GPUControlSnapshotScope):
        targets = (targets.target,)
        require_distinct_control_targets(targets)
    elif isinstance(targets, GPUControlMetadataScope):
        scope = targets
    else:
        require_distinct_control_targets(targets)
    device_ids = (
        targets.device_ids
        if isinstance(targets, GPUControlMetadataScope)
        else tuple(target.device_id for target in targets)
    )
    return device_ids, scope


@dataclass(frozen=True, slots=True)
class GPUControlFinalizationDependencies:
    gpu_services: GpuServiceDependencies
    dirty_flag_path: str

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUControlFinalizationDependencies",
            gpu_services=self.gpu_services,
            dirty_flag_path=self.dirty_flag_path,
        )


def finalize_gpu_control_effects(
    deps: GPUControlFinalizationDependencies, outcome: GPUControlOperationOutcome
) -> GPUControlOperationOutcome:
    if not outcome.requires_invalidation:
        return outcome
    failures: list[Exception] = []
    if outcome.requires_dirty_marker:
        try:
            receipt = establish_gpu_dirty_marker_receipt(
                deps.dirty_flag_path, outcome.dirty_marker_receipt
            )
            outcome = replace(outcome, dirty_marker_receipt=receipt)
        except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
            failures.append(exception)
    invalidations = (
        partial(
            deps.gpu_services.gpu_info_cache_service.invalidate_cache,
            owner="hardware.gpu_control.finalization",
            reason="native_effects_finalized",
        ),
        deps.gpu_services.gpu_vendor_detection_service.invalidate_cache,
        deps.gpu_services.nvidia_capabilities_cache_service.clear,
    )
    for invalidate in invalidations:
        try:
            invalidate()
        except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
            failures.append(exception)
    if not failures:
        return outcome
    if outcome.failure is not None:
        failures.insert(0, outcome.failure)
    failure = (
        failures[0]
        if len(failures) == 1
        else ExceptionGroup("GPU native effects finalization failed.", failures)
    )
    return replace(
        outcome,
        failure=failure,
        payload=failed_gpu_control_payload(outcome),
    )


def execute_finalized_gpu_control_worker(
    deps: GPUControlFinalizationDependencies,
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
    cancellation: CancellationTokenProtocol,
    *,
    metadata_scope: GPUControlMetadataScope | None,
) -> GPUControlOperationOutcome:
    try:
        outcome = worker(cancellation)
        if not isinstance(outcome, GPUControlOperationOutcome):
            raise ValidationError("GPU worker returned no typed terminal evidence.")
        if metadata_scope is not None:
            outcome.require_metadata_only()
    except TaskCancelledError:
        raise
    except GPUSlotWriteError as slot_exception:
        uncertain = slot_exception.reason == GPUSlotWriteFailure.PERSISTENCE_UNCERTAIN
        outcome = GPUControlOperationOutcome(
            build_gpu_operation_error(
                "apply_failed", "GPU slot metadata could not be saved safely."
            ),
            () if metadata_scope is not None else (GPUControlReduction(None, True, False, False),),
            uncertain if metadata_scope is not None else False,
            uncertain,
            slot_exception,
            False,
            (),
            (),
            (),
            None,
            None,
        )
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        outcome = GPUControlOperationOutcome(
            build_gpu_operation_error("apply_failed", "GPU settings could not be applied safely."),
            () if metadata_scope is not None else (GPUControlReduction(None, True, False, False),),
            None if metadata_scope is not None else False,
            metadata_scope is not None,
            exception,
            False,
            (),
            (),
            (),
            None,
            startup_result=None,
        )
    try:
        return finalize_gpu_control_effects(deps, outcome)
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        failure = (
            exception
            if outcome.failure is None
            else ExceptionGroup("GPU worker and finalization failed.", [outcome.failure, exception])
        )
        return replace(outcome, failure=failure, payload=failed_gpu_control_payload(outcome))

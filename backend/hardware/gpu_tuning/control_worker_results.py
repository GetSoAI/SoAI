"""SoAI - Private GPU worker completion and truthful terminal effects [backend/hardware/gpu_tuning/control_worker_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exceptions import ValidationError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.gpu_operation_results import build_gpu_operation_error
from hardware.gpu_tuning.mutation_leases import GPUControlMetadataScope
from hardware.gpu_tuning.native_startup_reconciliation import verify_observed_empty_startup_scope
from hardware.gpu_tuning.startup_scope_accounting import startup_cleanup_targets
from hardware.gpu_tuning.startup_scope_types import GPUControlStartupScope

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.hardware.gpu_control_operation_types import GPUControlPreflightRejection
    from core.hardware.gpu_control_types import (
        GPUControlCommitAcknowledgement,
        GPUControlDirtyMarkerReceipt,
        GPUControlReduction,
        GPUControlResult,
        GPUControlStartupResult,
    )
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GPUStartupAcquisitionResources

__all__ = (
    "GPUControlOperationCompletion",
    "GPUControlOperationOutcome",
    "GPUControlWorkerCompletion",
    "GPUControlWorkerState",
    "execute_control_worker",
    "failed_gpu_control_payload",
)


GPU_CONTROL_WORKER_EXCEPTIONS: tuple[type[Exception], ...] = (
    *HANDLED_RUNTIME_EXCEPTIONS,
    ExceptionGroup,
)


@dataclass(frozen=True, slots=True)
class GPUControlOperationOutcome:
    payload: JSONDict
    reductions: tuple[GPUControlReduction, ...]
    metadata_changed: bool | None
    persistence_uncertain: bool
    failure: Exception | None
    cancelled: bool
    native_results: tuple[GPUControlResult, ...]
    preflight_rejections: tuple[GPUControlPreflightRejection, ...]
    committed: tuple[GPUControlCommitAcknowledgement, ...]
    dirty_marker_receipt: GPUControlDirtyMarkerReceipt | None
    startup_result: GPUControlStartupResult | None

    def require_metadata_only(self) -> None:
        native_outcomes_present = bool(
            self.reductions or self.native_results or self.preflight_rejections or self.committed
        )
        if (
            native_outcomes_present
            or self.dirty_marker_receipt is not None
            or self.startup_result is not None
        ):
            raise ValidationError("GPU metadata cannot carry native or startup authority.")

    @property
    def changed(self) -> bool | None:
        if self.metadata_changed is True or any(
            reduction.changed is True for reduction in self.reductions
        ):
            return True
        if self.metadata_changed is None or any(
            reduction.changed is None for reduction in self.reductions
        ):
            return None
        return False

    @property
    def requires_invalidation(self) -> bool:
        return (
            self.persistence_uncertain
            or self.changed is not False
            or any(reduction.unresolved for reduction in self.reductions)
        )

    @property
    def requires_dirty_marker(self) -> bool:
        return any(
            reduction.changed is not False or reduction.unresolved for reduction in self.reductions
        )


@dataclass(frozen=True, slots=True)
class GPUControlOperationCompletion:
    outcome: GPUControlOperationOutcome | None
    failure: Exception | None
    cancelled: bool

    @property
    def failed(self) -> bool:
        return self.failure is not None


@dataclass(frozen=True, slots=True)
class GPUControlWorkerCompletion:
    outcome: GPUControlOperationOutcome | None
    failure: Exception | None
    cancelled: bool


@dataclass(slots=True)
class GPUControlWorkerState:
    cancellation: CancellationTokenProtocol
    entered: Event
    dispatched: bool = False


def execute_control_worker(
    worker: Callable[[CancellationTokenProtocol], GPUControlOperationOutcome],
    state: GPUControlWorkerState,
    scope: GPUControlStartupScope | GPUControlMetadataScope | None = None,
    startup_resources: GPUStartupAcquisitionResources | None = None,
) -> GPUControlWorkerCompletion:
    state.entered.set()
    try:
        state.cancellation.raise_if_cancelled()
        if isinstance(scope, GPUControlStartupScope) and not startup_cleanup_targets(scope):
            if startup_resources is None:
                raise ValidationError("GPU startup verification lacks acquisition authority.")
            verify_observed_empty_startup_scope(
                scope,
                executor=startup_resources.executor,
                logger=startup_resources.logger,
                gpu_services=startup_resources.gpu_services,
                acquisition_id=f"{scope.physical_snapshot.acquisition_id}:owned-entry",
            )
            state.cancellation.raise_if_cancelled()
        outcome = worker(state.cancellation)
        if not isinstance(outcome, GPUControlOperationOutcome):
            raise ValidationError("GPU worker returned an invalid typed terminal outcome.")
        if isinstance(scope, GPUControlMetadataScope):
            outcome.require_metadata_only()
        return GPUControlWorkerCompletion(outcome, outcome.failure, outcome.cancelled)
    except TaskCancelledError:
        return GPUControlWorkerCompletion(None, None, True)
    except GPU_CONTROL_WORKER_EXCEPTIONS as exception:
        return GPUControlWorkerCompletion(None, exception, False)


def failed_gpu_control_payload(outcome: GPUControlOperationOutcome) -> JSONDict:
    payload = copy.deepcopy(outcome.payload)
    payload.update(
        build_gpu_operation_error("apply_failed", "GPU settings could not be applied safely.")
    )
    results = payload.get("gpus")
    if isinstance(results, dict):
        for entry in results.values():
            if isinstance(entry, dict):
                errors = entry.get("errors")
                entry["errors"] = (
                    [*errors, "GPU operation finalization failed."]
                    if isinstance(errors, list)
                    else ["GPU operation finalization failed."]
                )
                entry.pop("applied_at", None)
    payload.pop("applied_at", None)
    if outcome.changed is None:
        payload.pop("changed", None)
    else:
        payload["changed"] = outcome.changed
    return payload

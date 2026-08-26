"""SoAI - Cancellation operations for in-flight orchestrator inference tasks [backend/orchestrator/execution/cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.context import create_system_cancellation_id
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from core.tasks.task import Task
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from orchestrator.execution.active_inferences import ActiveInferenceInfo
from orchestrator.execution.dependencies import InflightCancellationManagerDependencies
from orchestrator.execution.internal_protocols import ActiveInferenceRegistryProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CancelledInferenceCleanupInfo",
    "InflightCancellationManager",
    "InflightCleanupIntent",
)

LOGGER_NAME = "SoAI.orchestrator.execution.cancellation"
OPERATION_ORCHESTRATOR_CLEANUP_CANCELLED_INFERENCE = "orchestrator.cleanup_cancelled_inference"
OPERATION_ORCHESTRATOR_CLEANUP_CANCELLED_INFERENCE_FINALIZE = (
    "orchestrator.cleanup_cancelled_inference.finalize"
)


class CancelledInferenceCleanupInfo(TypedDict):
    plugin_name: str
    tracking_id: str
    task_id: str


@dataclass(frozen=True, slots=True)
class InflightCleanupIntent:
    reason: str
    should_fail: bool
    allow_failover: bool
    error_type: ErrorType


class InflightCancellationManager:
    def __init__(self, deps: InflightCancellationManagerDependencies) -> None:
        self._active_inferences: ActiveInferenceRegistryProtocol = deps.active_inferences
        self._task_registry: TaskRegistryProtocol = deps.task_registry
        self._cancellation_binder: TaskCancellationBinderProtocol = deps.cancellation_binder
        self._finalizer_tracker: TaskFinalizerTrackerProtocol = deps.finalizer_tracker
        self._cancel_task: Callable[[Task, str], Awaitable[None]] = deps.cancel_task
        self._fail_task = deps.fail_task
        self._cleanup_intents: dict[str, InflightCleanupIntent] = {}

    def cancel_inflight(
        self,
        info: ActiveInferenceInfo | None,
        *,
        prefix: str,
        reason: str,
    ) -> None:
        self._schedule_cleanup(
            info,
            prefix=prefix,
            reason=reason,
            should_fail=False,
            allow_failover=False,
            error_type=ErrorType.SERVER_ERROR,
        )

    def fail_inflight(
        self,
        info: ActiveInferenceInfo | None,
        *,
        prefix: str,
        reason: str,
        allow_failover: bool,
        error_type: ErrorType,
    ) -> None:
        self._schedule_cleanup(
            info,
            prefix=prefix,
            reason=reason,
            should_fail=True,
            allow_failover=allow_failover,
            error_type=error_type,
        )

    def has_cleanup_intent(self, tracking_id: str) -> bool:
        return tracking_id in self._cleanup_intents

    def _schedule_cleanup(
        self,
        info: ActiveInferenceInfo | None,
        *,
        prefix: str,
        reason: str,
        should_fail: bool,
        allow_failover: bool,
        error_type: ErrorType,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        if info is None:
            return
        task = info["task"]
        task_id = info["task_id"]
        if task is not None and (not task.done()):
            task.cancel()
            if not task_id:
                logger.warning(
                    "%sActively cancelled in-flight inference task with missing task_id.",
                    prefix,
                )
            else:
                logger.info(
                    "%sActively cancelled in-flight inference task for %s.",
                    prefix,
                    task_id,
                )
        plugin_name = info["plugin_name"]
        tracking_id = info["tracking_id"]
        if plugin_name and tracking_id and task_id:
            spawn_cleanup = self._register_cleanup_intent(
                tracking_id=tracking_id,
                reason=reason,
                should_fail=should_fail,
                allow_failover=allow_failover,
                error_type=error_type,
            )
            if not spawn_cleanup:
                return
            info_copy: CancelledInferenceCleanupInfo = {
                "plugin_name": plugin_name,
                "tracking_id": tracking_id,
                "task_id": task_id,
            }
            cleanup_cancellation_id = create_system_cancellation_id(
                f"orchestrator_cancel_cleanup:{plugin_name}:{tracking_id}",
            )
            metadata: JSONDict = {"plugin": plugin_name}
            _ = spawn_tracked_task(
                self._cleanup_cancelled_inference(info_copy),
                name=f"orchestrator-cancel-cleanup-{plugin_name}-{tracking_id}",
                owner="cancel_cleanup",
                logger=logger,
                metadata=metadata,
                cancellation_id=cleanup_cancellation_id,
                cancellation_binder=self._cancellation_binder,
                finalizer_tracker=self._finalizer_tracker,
            )

    def _register_cleanup_intent(
        self,
        *,
        tracking_id: str,
        reason: str,
        should_fail: bool,
        allow_failover: bool,
        error_type: ErrorType,
    ) -> bool:
        existing = self._cleanup_intents.get(tracking_id)
        normalized_reason = reason or "Cancelled"
        if existing is None:
            self._cleanup_intents[tracking_id] = InflightCleanupIntent(
                reason=normalized_reason,
                should_fail=should_fail,
                allow_failover=allow_failover,
                error_type=error_type,
            )
            return True
        if should_fail and not existing.should_fail:
            self._cleanup_intents[tracking_id] = InflightCleanupIntent(
                reason=normalized_reason,
                should_fail=True,
                allow_failover=allow_failover,
                error_type=error_type,
            )
            return False
        if should_fail and existing.should_fail:
            self._cleanup_intents[tracking_id] = InflightCleanupIntent(
                reason=normalized_reason,
                should_fail=True,
                allow_failover=existing.allow_failover and allow_failover,
                error_type=error_type,
            )
            return False
        return False

    async def _cleanup_cancelled_inference(self, info: CancelledInferenceCleanupInfo) -> None:
        logger = get_logger(LOGGER_NAME)
        plugin_name = info["plugin_name"]
        tracking_id = info["tracking_id"]
        task_id = info["task_id"]
        intent = self._cleanup_intents.get(tracking_id)
        reason = intent.reason if intent is not None else "Cancelled"
        should_fail = intent.should_fail if intent is not None else False
        allow_failover = intent.allow_failover if intent is not None else False
        error_type = intent.error_type if intent is not None else ErrorType.SERVER_ERROR
        try:
            if tracking_id:
                await self._active_inferences.pop(tracking_id)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Failed to cleanup cancelled inference for task {task_id}",
                operation=OPERATION_ORCHESTRATOR_CLEANUP_CANCELLED_INFERENCE,
                details={
                    "plugin_name": plugin_name,
                    "tracking_id": tracking_id,
                },
            )
        finally:
            if task_id:
                try:
                    registry = self._task_registry
                    task = await uncancel_then_cleanup(registry.get(task_id))
                    if task is None:
                        cancel_reason = str(reason or "").strip() or "Cancelled by user"
                        await uncancel_then_cleanup(
                            finalize(
                                registry,
                                task_id,
                                TaskStatus.FAILED if should_fail else TaskStatus.CANCELLED,
                                error_message=cancel_reason,
                                status_message=cancel_reason,
                            ),
                        )
                    elif not task.status.is_terminal():
                        if is_orchestrated_inference_task_type(task.task_type):
                            if task.orchestration_context is None:
                                task = task.with_orchestration_context(
                                    OrchestrationContext(tracking_id=tracking_id),
                                )
                                await uncancel_then_cleanup(registry.update_task_cache(task))
                            if should_fail:
                                await uncancel_then_cleanup(
                                    self._fail_task(
                                        task,
                                        reason,
                                        allow_failover=allow_failover,
                                        error_type=error_type,
                                    ),
                                )
                            else:
                                await uncancel_then_cleanup(self._cancel_task(task, reason))
                        else:
                            cancel_reason = str(reason or "").strip() or "Cancelled by user"
                            await uncancel_then_cleanup(
                                finalize(
                                    registry,
                                    task_id,
                                    TaskStatus.FAILED if should_fail else TaskStatus.CANCELLED,
                                    error_message=cancel_reason,
                                    status_message=cancel_reason,
                                ),
                            )
                except RECOVERABLE_EXCEPTIONS as finalize_exc:
                    log_exception(
                        logger,
                        finalize_exc,
                        message=f"Failed to finalize cancelled task {task_id}",
                        operation=OPERATION_ORCHESTRATOR_CLEANUP_CANCELLED_INFERENCE_FINALIZE,
                        level="warning",
                    )
                finally:
                    if tracking_id:
                        self._cleanup_intents.pop(tracking_id, None)

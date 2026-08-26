"""SoAI - Orchestrator inference execution coordinator [backend/orchestrator/execution/inference_executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import PayloadTooLargeError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.protocols_queue import QueueCycleType
from core.orchestrator.routing_config import RoutingConfig, require_routing_config
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.enums import TaskStatus
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.orchestration_persistence import persist_with_logging
from core.tasks.status_transitions import update_status
from core.tasks.task import Task
from orchestrator.execution.accepted_inference_failure import (
    terminalize_unexpected_accepted_inference,
)
from orchestrator.execution.active_inferences import ActiveInferenceInfo
from orchestrator.execution.event_context import (
    extract_event_context_as_dict,
    is_streaming_request,
)
from orchestrator.execution.inference_executor_dependencies import (
    OrchestratorInferenceExecutorDependencies,
)
from orchestrator.execution.inference_runtime_resolution import (
    resolve_inference_runtime_instance,
)
from orchestrator.execution.requeue import RequeueTask
from orchestrator.execution.task_creation import create_linked_task

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("OrchestratorInferenceExecutor",)

LOGGER_NAME = "SoAI.orchestrator.execution.inference_executor"
OPERATION = "orchestrator.dispatch_and_stream_response"


class OrchestratorInferenceExecutor:
    def __init__(self, deps: OrchestratorInferenceExecutorDependencies) -> None:
        self._deps = deps.orchestrator
        self._routing_config: RoutingConfig | None = deps.routing_config
        self.queue = deps.queue
        self.lifecycle = deps.lifecycle
        self.task_registry = deps.task_registry
        self.health_check_config = deps.config.health_check_config
        self.conservative_billing_threshold = deps.config.conservative_billing_threshold
        self._results = deps.results
        self._engine = deps.engine
        self._outcomes = deps.outcomes
        self._metrics = deps.orchestrator.metrics
        self._active_inferences = deps.active_inferences
        self._cancellations = deps.cancellations
        self.last_logged_config: dict[str, tuple[str, tuple[JSONDict, int] | None]] = {}
        self._last_logged_config_lock = asyncio.Lock()

    @property
    def routing_config(self) -> RoutingConfig:
        return require_routing_config(self._routing_config)

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None:
        self._routing_config = value

    def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self.health_check_config = config.health_check_config
        self.conservative_billing_threshold = config.conservative_billing_threshold
        self._results.update_config(self.health_check_config, self.conservative_billing_threshold)
        self._engine.update_config(self.health_check_config)

    async def execute_inference_on_task(
        self,
        task: Task,
        plugin_name: str,
        model_info: JSONDict,
    ) -> bool:
        logger = get_logger(LOGGER_NAME)
        plugin_instance = None
        tracking_id: str | None = None
        try:
            context = self.queue.require_orchestration_context(task)
            tracking_id = context.tracking_id
            registry = self.task_registry
            plugin_instance = await resolve_inference_runtime_instance(
                plugin_name=plugin_name,
                model_info=model_info,
                task=task,
                plugin_manager=self._deps.plugin_manager,
                state_aggregator=self._deps.state_aggregator,
                lifecycle=self.lifecycle,
                outcomes=self._outcomes,
                logger=logger,
            )
            if plugin_instance is None:
                return False
            processing_task = await update_status(registry, task.task_id, TaskStatus.PROCESSING)
            if processing_task is None:
                return False
            task = processing_task
            context = self.queue.require_orchestration_context(task)
            try:
                success, _ = await persist_with_logging(
                    registry,
                    task.task_id,
                    logger=logger,
                    operation="orchestrator.execute_inference",
                )
                if not success:
                    await self._outcomes.fail_task(
                        task,
                        TASK_STATE_PERSISTENCE_FAILED_MESSAGE,
                        allow_failover=False,
                    )
                    return False
                model_uid_value = model_info.get("universal_id")
                if not isinstance(model_uid_value, str) or not model_uid_value:
                    raise StateError("Model info missing universal_id.")
                new_config_fingerprint = (
                    model_uid_value,
                    context.parameter_snapshot,
                )
                should_log_config = False
                async with self._last_logged_config_lock:
                    if self.last_logged_config.get(plugin_name) != new_config_fingerprint:
                        self.last_logged_config[plugin_name] = new_config_fingerprint
                        should_log_config = True
                if should_log_config:
                    await self.lifecycle.task_tracking.log_task_configuration(task, model_info)
                metadata_for_binding: JSONDict = {
                    "plugin": plugin_name,
                    "model_uid": model_info["universal_id"],
                }
                execute_task = create_linked_task(
                    self._engine.execute_task(task, plugin_instance, model_info),
                    cancellation_binder=self._deps.task_cancellation_binder,
                    cancellation_id=task.cancellation_id,
                    owner="inference",
                    name=f"orchestrator-execute-{task.task_id}",
                    logger=logger,
                    finalizer_tracker=self._deps.task_finalizer_tracker,
                    metadata=metadata_for_binding,
                    owner_observes_result=True,
                )
                inference_info: ActiveInferenceInfo = {
                    "tracking_id": context.tracking_id,
                    "task_id": task.task_id,
                    "cancellation_id": task.cancellation_id,
                    "context": extract_event_context_as_dict(context),
                    "plugin_name": plugin_name,
                    "model_uid": model_uid_value,
                    "start_time": time.monotonic(),
                    "last_progress_time": time.monotonic(),
                    "stream_activity_seen": False,
                    "is_streaming": is_streaming_request(context),
                    "is_persistent": plugin_instance.PERSISTENT,
                    "reply_channel": task.reply_queue,
                    "task": execute_task,
                }
                await self._active_inferences.register(
                    context.tracking_id,
                    inference_info,
                )
                result = await execute_task
                return bool(result)
            except RequeueTask:
                logger.warning(
                    "Task [%s] is being re-queued due to a last-moment plugin state change for '%s'.",
                    task.task_id,
                    plugin_name,
                )
                return False
            except asyncio.CancelledError:
                logger.warning("Task [%s] was cancelled during execution.", task.task_id)
                current_task = asyncio.current_task()
                was_task_cancelled = bool(current_task and current_task.cancelling())

                async def _handle_cancellation() -> None:
                    task_snapshot = await self.task_registry.get(task.task_id)
                    if task_snapshot is not None and task_snapshot.status.is_terminal():
                        return
                    if tracking_id and self._cancellations.has_cleanup_intent(tracking_id):
                        return
                    await self._outcomes.cancel_task(task, "Task was cancelled by system or user.")

                await uncancel_then_cleanup(_handle_cancellation())
                current_task = asyncio.current_task()
                if was_task_cancelled or (current_task is not None and current_task.cancelling()):
                    raise
                return False
            except PayloadTooLargeError as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message=f"Task execution request exceeded the IPC payload budget [{task.task_id}]",
                    operation=OPERATION,
                    level="warning",
                )
                await self._outcomes.fail_task(
                    task,
                    str(exception),
                    allow_failover=False,
                    error_type=ErrorType.INVALID_REQUEST,
                )
                return False
            except RECOVERABLE_EXCEPTIONS as exception:
                coerced_exception = coerce_to_soai_error(
                    exception,
                    operation="orchestrator.dispatch_and_stream_response",
                )
                log_exception(
                    logger,
                    coerced_exception,
                    message=f"Unhandled exception during task execution [{task.task_id}]",
                    operation=OPERATION,
                )
                await self._outcomes.fail_task(
                    task,
                    f"Core execution error: {coerced_exception}",
                    allow_failover=False,
                )
                return False
            finally:
                if tracking_id is not None:
                    await uncancel_then_cleanup(self._active_inferences.pop(tracking_id))
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION)
            log_exception(
                logger,
                coerced,
                message="Unexpected accepted inference dispatch failure.",
                operation=OPERATION,
                details={"task_id": task.task_id},
                level="error",
            )
            return await terminalize_unexpected_accepted_inference(
                task_registry=self.task_registry,
                outcomes=self._outcomes,
                task=task,
                logger=logger,
                operation=OPERATION,
            )
        finally:
            await uncancel_then_cleanup(self.queue.cycles.close_cycle(task, QueueCycleType.PLUGIN))

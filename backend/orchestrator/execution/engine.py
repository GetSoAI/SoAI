"""SoAI - Task execution engine with timeout and error handling [backend/orchestrator/execution/engine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.config.numeric import coerce_positive_float
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.licensing.admission import LicensingOperationClass
from core.licensing.enforcement import LICENSING_RESTRICTED_MESSAGE
from core.licensing.protocols import LicensingStatusProtocol
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.model_info_fields import coerce_plugin_name
from core.models.provider_backing import is_provider_backed_model
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.protocols import StateAggregatorProtocol
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from orchestrator.capacity.slot_lease import PluginSlotLease
from orchestrator.execution.accepted_inference_failure import (
    terminalize_unexpected_accepted_inference,
)
from orchestrator.execution.dependencies import (
    ExecutorEngineDependencies,
)
from orchestrator.execution.engine_active_registration_repair import (
    repair_active_registered_from_membership,
)
from orchestrator.execution.engine_failure_handling import handle_execution_failure
from orchestrator.execution.engine_task_cleanup import cleanup_task_execution
from orchestrator.execution.internal_protocols import (
    ActiveInferenceRegistryProtocol,
    InferencePayloadPreparerProtocol,
    OutcomeManagerProtocol,
    ResultProcessorProtocol,
)
from orchestrator.execution.plugin_cancellation_notification import (
    notify_plugin_task_cancelled,
)
from orchestrator.execution.plugin_slot_dispatch import execute_task_within_plugin_slot
from orchestrator.execution.requeue import RequeueTask
from orchestrator.internal_protocols import OrchestratorCapacityProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from orchestrator.execution.chat_template_role_policy import (
        ChatTemplateRolePolicyResolver,
    )

__all__ = ("ExecutorEngine",)

LOGGER_NAME = "SoAI.orchestrator.execution.engine"
OPERATION_ORCHESTRATOR_TASK_EXECUTION = "orchestrator.task_execution"
_EXECUTION_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    httpx2.HTTPStatusError,
    *HTTP_RECOVERABLE_EXCEPTIONS,
)


class ExecutorEngine:
    def __init__(self, deps: ExecutorEngineDependencies) -> None:
        self._queue: QueueServiceView = deps.queue
        self._lifecycle: OrchestratorLifecycleCoordinatorProtocol = deps.lifecycle
        self._capacity: OrchestratorCapacityProtocol = deps.capacity
        self._task_registry: TaskRegistryProtocol = deps.task_registry
        self._state_aggregator: StateAggregatorProtocol = deps.state_aggregator
        self._active_inferences: ActiveInferenceRegistryProtocol = deps.active_inferences
        self._payload_preparer: InferencePayloadPreparerProtocol = deps.payload_preparer
        self._results: ResultProcessorProtocol = deps.results
        self._outcomes: OutcomeManagerProtocol = deps.outcomes
        self._metrics: MetricsManagerProtocol = deps.metrics
        self._health_check_config: JSONDict = deps.health_check_config
        self._role_policy_resolver: ChatTemplateRolePolicyResolver = deps.role_policy_resolver
        self._licensing_status: LicensingStatusProtocol = deps.licensing_status
        self._requeue_inside_slot_warners: dict[str, RateLimitedLogger] = {}

    def update_config(self, health_check_config: JSONDict) -> None:
        self._health_check_config = health_check_config

    async def execute_task(
        self,
        task: Task,
        plugin_instance: PluginInstanceProtocol,
        model_info: JSONDict,
    ) -> bool:
        logger = get_logger(LOGGER_NAME)
        admission = await self._licensing_status.admission(LicensingOperationClass.ORDINARY)
        if not admission.allowed:
            await self._outcomes.fail_task(
                task,
                LICENSING_RESTRICTED_MESSAGE,
                allow_failover=False,
            )
            return False
        plugin_name = coerce_plugin_name(model_info)
        if plugin_name is None:
            await self._outcomes.fail_task(
                task,
                "Model info missing plugin name.",
                allow_failover=False,
            )
            return False
        model_uid_value = model_info.get("universal_id")
        if not isinstance(model_uid_value, str) or not model_uid_value:
            await self._outcomes.fail_task(
                task,
                "Model info missing universal_id.",
                allow_failover=False,
            )
            return False
        request_timeout = float(LONG_REQUEST_TIMEOUT_SEC)
        active_registered = False
        completed = False
        cancelled = False
        tracking_id: str | None = None
        is_persistent = bool(plugin_instance.PERSISTENT)
        stored_cancellation: asyncio.CancelledError | None = None
        slot_lease = PluginSlotLease.noop(plugin_name)
        try:
            logger.trace(
                "Task %s waiting for concurrency slot on plugin '%s'.",
                task.task_id,
                plugin_name,
            )
            request_timeout = coerce_positive_float(
                self._health_check_config.get(
                    "NON_STREAMING_TIMEOUT_SEC",
                    LONG_REQUEST_TIMEOUT_SEC,
                ),
                default=LONG_REQUEST_TIMEOUT_SEC,
                minimum=0.0,
                label="MODELS.ROUTING.HEALTH_CHECKS.NON_STREAMING_TIMEOUT_SEC",
                logger=logger,
            )
            context = self._queue.require_orchestration_context(task)
            if task.orchestration_context is None:
                task = task.with_orchestration_context(context)
            tracking_id = context.tracking_id
            if not tracking_id:
                await self._outcomes.fail_task(
                    task,
                    "Missing tracking id for task",
                    allow_failover=False,
                )
                return False
            event = context.event
            if event is None:
                await self._outcomes.fail_task(
                    task,
                    "Missing inference event for task",
                    allow_failover=False,
                )
                return False
            slot_lease = await self._capacity.acquire_plugin_slot(plugin_name)
            async with slot_lease:
                active_registered = (
                    await self._lifecycle.task_tracking.try_register_compatible_task_start(
                        plugin_name,
                        tracking_id,
                        model_uid_value,
                        dict(context.startup_params),
                        provider_backed=is_provider_backed_model(model_info),
                        persistent_runtime=is_persistent,
                    )
                )
                task, completed = await execute_task_within_plugin_slot(
                    self._queue,
                    self._task_registry,
                    self._state_aggregator,
                    self._active_inferences,
                    self._payload_preparer,
                    self._results,
                    self._outcomes,
                    self._metrics,
                    self._role_policy_resolver,
                    lifecycle=self._lifecycle,
                    requeue_inside_slot_warners=self._requeue_inside_slot_warners,
                    admission_registered=active_registered,
                    task=task,
                    plugin_name=plugin_name,
                    plugin_instance=plugin_instance,
                    tracking_id=tracking_id,
                    request_timeout=request_timeout,
                    health_check_config=self._health_check_config,
                    model_info=model_info,
                    event=event,
                    logger=logger,
                )
                return completed
        except RequeueTask:
            return False
        except asyncio.CancelledError as cancellation_exception:
            cancelled = True
            stored_cancellation = cancellation_exception
            if task.orchestration_context is not None:
                await uncancel_then_cleanup(
                    notify_plugin_task_cancelled(
                        task=task,
                        plugin_instance=plugin_instance,
                        plugin_name=plugin_name,
                        context_source=task.orchestration_context,
                        logger=logger,
                    ),
                )
            active_registered = await uncancel_then_cleanup(
                repair_active_registered_from_membership(
                    lifecycle=self._lifecycle,
                    plugin_name=plugin_name,
                    tracking_id=tracking_id,
                    active_registered=active_registered,
                    logger=logger,
                    task_id=task.task_id,
                ),
            )
            return False
        except _EXECUTION_FAILURE_EXCEPTIONS as exception:
            return await handle_execution_failure(
                queue=self._queue,
                lifecycle=self._lifecycle,
                state_aggregator=self._state_aggregator,
                outcomes=self._outcomes,
                task=task,
                plugin_instance=plugin_instance,
                plugin_name=plugin_name,
                exception=exception,
                request_timeout=request_timeout,
            )
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_ORCHESTRATOR_TASK_EXECUTION,
            )
            log_exception(
                logger,
                coerced,
                message="Unexpected accepted inference execution failure.",
                operation=OPERATION_ORCHESTRATOR_TASK_EXECUTION,
                details={"task_id": task.task_id},
                level="error",
            )
            return await terminalize_unexpected_accepted_inference(
                task_registry=self._task_registry,
                outcomes=self._outcomes,
                task=task,
                logger=logger,
                operation=OPERATION_ORCHESTRATOR_TASK_EXECUTION,
            )
        finally:
            active_registered = await uncancel_then_cleanup(
                repair_active_registered_from_membership(
                    lifecycle=self._lifecycle,
                    plugin_name=plugin_name,
                    tracking_id=tracking_id,
                    active_registered=active_registered,
                    logger=logger,
                    task_id=task.task_id,
                ),
            )
            await uncancel_then_cleanup(
                cleanup_task_execution(
                    lifecycle=self._lifecycle,
                    active_inferences=self._active_inferences,
                    plugin_name=plugin_name,
                    tracking_id=tracking_id,
                    task_id=task.task_id,
                    completed=completed,
                    cancelled=cancelled,
                    is_persistent=is_persistent,
                    active_registered=active_registered,
                    slot_lease=slot_lease,
                ),
            )
            if stored_cancellation is not None:
                raise stored_cancellation

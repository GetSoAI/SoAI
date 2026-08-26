"""SoAI - Runtime plugin resolution for accepted inference [backend/orchestrator/execution/inference_runtime_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.models.provider_backing import is_provider_backed_model
from core.state.state_transition_sets import DISPATCH_READY_STATES
from orchestrator.scheduling.dispatch_runtime_invariant import (
    ensure_dispatch_runtime_instance,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.plugins.protocols import PluginManagerProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.protocols import StateAggregatorProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from orchestrator.execution.internal_protocols import OutcomeManagerProtocol
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )

__all__ = ("resolve_inference_runtime_instance",)

OPERATION = "orchestrator.execution.inference_runtime_resolution"


async def resolve_inference_runtime_instance(
    *,
    plugin_name: str,
    model_info: JSONDict,
    task: Task,
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    outcomes: OutcomeManagerProtocol,
    logger: TraceLogger,
) -> PluginInstanceProtocol | None:
    plugin_instance = await plugin_manager.get_plugin_instance(plugin_name)
    if plugin_instance is not None:
        return plugin_instance
    if is_provider_backed_model(model_info):
        try:
            return await plugin_manager.require_loaded_plugin(plugin_name, auto_load=True)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to hydrate provider-backed plugin runtime before execution.",
                operation=OPERATION,
                details={"plugin": plugin_name, "task_id": task.task_id},
                level="warning",
            )
            await outcomes.fail_task(
                task,
                "The provider-backed model backend is not available.",
                allow_failover=False,
                error_type=ErrorType.PLUGIN_UNAVAILABLE,
            )
            return None
    runtime_guard = await ensure_dispatch_runtime_instance(
        plugin_name=plugin_name,
        provider_backed=False,
        plugin_manager=plugin_manager,
        state_aggregator_get_status=state_aggregator.get_plugin_status,
        lifecycle_publish_state_change=lifecycle.publisher.publish_runtime_state_change,
        dispatch_ready_states=set(DISPATCH_READY_STATES),
        logger=logger,
    )
    if runtime_guard.plugin_instance is not None:
        return runtime_guard.plugin_instance
    failure = runtime_guard.failure
    await outcomes.fail_task(
        task,
        (
            failure.message
            if failure is not None
            else "The model backend changed state before execution."
        ),
        allow_failover=False,
        error_type=(failure.error_type if failure is not None else ErrorType.PLUGIN_UNAVAILABLE),
    )
    return None

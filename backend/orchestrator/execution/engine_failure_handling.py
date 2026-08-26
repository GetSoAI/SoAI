"""SoAI - Orchestrator executor failure classification and outcome handling [backend/orchestrator/execution/engine_failure_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx2

from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.openai.request_features import request_includes_tool_calling
from core.runtime.request_sources import REQUEST_SOURCE_MODEL_TEST
from core.state.state_names import (
    ORCH_STATE_ERROR,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_REMOVING_BACKEND,
)
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC
from orchestrator.execution.execution_http_response_readback import (
    drain_httpx_error_response_body,
)
from orchestrator.execution.failure_classification import classify_execution_failure
from orchestrator.execution.transport_failure_diagnostics import (
    sanitize_health_ping_detail,
)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.protocols import StateAggregatorProtocol
    from core.tasks.task import Task
    from orchestrator.execution.internal_protocols import OutcomeManagerProtocol
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )
    from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("handle_execution_failure",)

LOGGER_NAME = "SoAI.orchestrator.execution.engine_failure_handling"
OPERATION_ORCHESTRATOR_HANDLE_EXECUTION_FAILURE = "orchestrator.handle_execution_failure"
OPERATION_ORCHESTRATOR_HANDLE_EXECUTION_FAILURE_HEALTH_PING_ENRICHMENT = (
    "orchestrator.handle_execution_failure.health_ping_enrichment"
)


def _unwrap_generic_soai_error(exception: Exception) -> Exception:
    if isinstance(exception, SoAIError) and (exception.__class__ is SoAIError):
        cause_exception = exception.cause
        if isinstance(cause_exception, Exception):
            return cause_exception
    return exception


async def handle_execution_failure(
    *,
    queue: QueueServiceView,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    state_aggregator: StateAggregatorProtocol,
    outcomes: OutcomeManagerProtocol,
    task: Task,
    plugin_instance: PluginInstanceProtocol,
    plugin_name: str,
    exception: Exception,
    request_timeout: float,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    context = queue.require_orchestration_context(task)
    is_model_test_request = context.request_source == REQUEST_SOURCE_MODEL_TEST
    event = context.event
    if isinstance(exception, httpx2.HTTPStatusError):
        await drain_httpx_error_response_body(exception, logger=logger)
    if (
        isinstance(exception, httpx2.HTTPStatusError)
        and exception.response is not None
        and (exception.response.status_code == 404)
    ):
        requested_model = event.payload.get("model") if event else None
        user_message = f"Model '{requested_model}' is not available on plugin '{plugin_name}'."
        logger.warning("Task %s failed because model was not found on backend.", task.task_id)
        await outcomes.fail_task(
            task,
            user_message,
            allow_failover=False,
            error_type=ErrorType.NOT_FOUND,
            reason_is_public=True,
        )
        return False
    details = classify_execution_failure(task.task_id, exception, request_timeout)
    user_message = details.user_message
    error_type = details.error_type
    allow_failover = details.allow_failover
    if isinstance(exception, httpx2.HTTPStatusError) and exception.response is not None:
        status_code = exception.response.status_code
        payload = event.payload if event else {}
        tools_requested, tools_count = request_includes_tool_calling(
            payload if isinstance(payload, dict) else {},
        )
        if tools_requested and status_code in {400, 415, 422}:
            requested_model = payload.get("model") if isinstance(payload, dict) else None
            model_label = (
                requested_model
                if isinstance(requested_model, str) and requested_model
                else "unknown"
            )
            specific_message = details.user_message.strip()
            default_message = f"HTTP {status_code} error"
            if specific_message and specific_message != default_message:
                user_message = (
                    f"Backend rejected the tool-calling request (HTTP {status_code}). "
                    f"Backend message: {specific_message} "
                    f"Model: '{model_label}', plugin: '{plugin_name}', tools: {tools_count}."
                )
            else:
                user_message = (
                    f"Tool calling was requested, but the selected backend rejected the request (HTTP {status_code}). "
                    f"This may mean the backend or model does not support the submitted tool schema or tool_choice payload. "
                    f"Model: '{model_label}', plugin: '{plugin_name}', tools: {tools_count}. "
                    "Fix: inspect the backend error body, simplify the tool schema, disable tools/tool_choice, or select a different backend."
                )
            error_type = ErrorType.INVALID_REQUEST
            allow_failover = False
    root_exception = _unwrap_generic_soai_error(exception)
    if isinstance(root_exception, httpx2.RequestError):
        payload = event.payload if event else {}
        tools_requested, tools_count = request_includes_tool_calling(
            payload if isinstance(payload, dict) else {},
        )
        if tools_requested:
            user_message = (
                f"{user_message} Hint: tool calling was requested ({tools_count} tools). "
                "Some backends disconnect when rejecting unsupported tool payloads. "
                "Try disabling tools/tool_choice or selecting a tool-capable model."
            )
        plugin_status = await state_aggregator.get_plugin_status(plugin_name)
        if plugin_status not in {PLUGIN_STATE_DELETING, PLUGIN_STATE_REMOVING_BACKEND}:
            try:
                is_healthy, health_message = await asyncio.wait_for(
                    plugin_instance.health_ping(),
                    timeout=RESPONSIVE_TIMEOUT_SEC,
                )
                if not is_healthy:
                    user_message = (
                        f"{user_message} Health: {sanitize_health_ping_detail(health_message)}"
                    )
            except HTTP_RECOVERABLE_EXCEPTIONS as ping_exception:
                coerced_ping_exception = coerce_to_soai_error(
                    ping_exception,
                    operation="orchestrator.handle_execution_failure.health_ping_enrichment",
                )
                log_exception(
                    logger,
                    coerced_ping_exception,
                    message="Health ping enrichment failed after transport error.",
                    operation=OPERATION_ORCHESTRATOR_HANDLE_EXECUTION_FAILURE_HEALTH_PING_ENRICHMENT,
                    details={"plugin": plugin_name, "task_id": task.task_id},
                    level="warning",
                )
                logger.debug(
                    "Health ping enrichment failed for '%s' after transport error.",
                    plugin_name,
                )
    if details.log_stack:
        log_exception(
            logger,
            exception,
            message=f"Error executing task {task.task_id}: {user_message}",
            operation=OPERATION_ORCHESTRATOR_HANDLE_EXECUTION_FAILURE,
        )
    else:
        logger.warning("Error executing task %s: %s", task.task_id, user_message)
    if details.affects_plugin_health and (not is_model_test_request):
        await lifecycle.circuit_breakers.record_cb_failure(plugin_name)
        if await state_aggregator.get_plugin_status(plugin_name) not in {
            PLUGIN_STATE_DELETING,
            PLUGIN_STATE_REMOVING_BACKEND,
        }:
            await lifecycle.publisher.publish_runtime_state_change(
                plugin_name,
                ORCH_STATE_ERROR,
                details.state_reason,
            )
        else:
            logger.warning(
                "Request failed during plugin removal for '%s'. Suppressing state change to ERROR.",
                plugin_name,
            )
    await outcomes.fail_task(
        task,
        user_message,
        allow_failover=allow_failover,
        error_type=error_type,
        reason_is_public=True,
    )
    return False

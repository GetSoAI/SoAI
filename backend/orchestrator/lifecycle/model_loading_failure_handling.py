"""SoAI - Model loading failure handling [backend/orchestrator/lifecycle/model_loading_failure_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAITimeoutError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.state.state_names import ORCH_STATE_ERROR, ORCH_STATE_STOPPED
from orchestrator.lifecycle.model_loading_cleanup import (
    stop_started_plugin_for_concurrent_lifecycle_state_change,
)
from orchestrator.lifecycle.model_loading_failure_classification import (
    classify_model_load_failure,
)
from orchestrator.lifecycle.model_loading_failure_publication import (
    publish_model_load_terminal_state_if_current,
)
from orchestrator.lifecycle.model_loading_result import ModelLoadingResult
from orchestrator.lifecycle.model_loading_transitions import (
    publish_model_load_stopped_terminal_state_if_valid,
)
from orchestrator.lifecycle.plugin_process_termination import (
    force_kill_plugin_backend_processes,
)
from orchestrator.lifecycle.state_transition_validation import (
    is_invalid_transition_error,
)
from orchestrator.lifecycle.tracked_backend_processes import (
    perform_tracked_plugin_stop_logic,
    supports_backend_process_tracking,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from orchestrator.lifecycle.model_loading_dependencies import (
        OrchestratorLifecycleModelLoadingDependencies,
    )

__all__ = ("handle_model_loading_exception",)

OPERATION = "orchestrator.start_plugin_and_load_model"


async def handle_model_loading_exception(
    deps: OrchestratorLifecycleModelLoadingDependencies,
    *,
    plugin_name: str,
    universal_id: str,
    load_timeout: float,
    exception: BaseException,
    logger: LoggerProtocol,
    started_process: bool,
    plugin_instance: PluginInstanceProtocol | None,
    is_model_test_request: bool,
) -> ModelLoadingResult:
    if is_invalid_transition_error(exception):
        log_exception(
            logger,
            exception,
            message="Aborting model load due to invalid runtime state transition (concurrent lifecycle change).",
            operation=OPERATION,
            details={"plugin": plugin_name},
            level="warning",
        )
        await stop_started_plugin_for_concurrent_lifecycle_state_change(
            deps,
            logger=logger,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            started_process=started_process,
        )
        return ModelLoadingResult.deferred()
    classification = classify_model_load_failure(exception)
    failure_context = "model-scoped load" if classification.model_scoped else "start/load"
    if deps.shutdown_event.is_set():
        await _terminate_model_load_backend(
            deps,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            logger=logger,
            failure_context=failure_context,
        )
        return ModelLoadingResult.deferred()
    if classification.model_scoped:
        log_exception(
            logger,
            exception,
            message=f"Model load failed for '{universal_id}' on plugin '{plugin_name}'.",
            operation=OPERATION,
            details={"plugin": plugin_name, "universal_id": universal_id},
            level="warning",
        )
        terminated = await _terminate_model_load_backend(
            deps,
            plugin_name=plugin_name,
            plugin_instance=plugin_instance,
            logger=logger,
            failure_context=failure_context,
        )
        if plugin_instance is None:
            await publish_model_load_terminal_state_if_current(
                deps,
                plugin_name=plugin_name,
                target_state=ORCH_STATE_STOPPED if terminated else ORCH_STATE_ERROR,
                reason=(
                    f"Model '{universal_id}' failed to load; plugin stopped. Reason: {classification.reason}"
                    if terminated
                    else f"Model '{universal_id}' failed to load and plugin cleanup failed. Reason: {classification.reason}"
                ),
                logger=logger,
            )
        else:
            await publish_model_load_stopped_terminal_state_if_valid(
                plugin_instance=plugin_instance,
                terminated=terminated,
                stopped_reason=f"Model '{universal_id}' failed to load; plugin stopped. Reason: {classification.reason}",
                failed_reason=f"Model '{universal_id}' failed to load and plugin cleanup failed. Reason: {classification.reason}",
                operation=f"orchestrator.start_plugin_and_load_model.failure.{plugin_name}.persistent",
                plugin_name=plugin_name,
                publisher=deps.lifecycle_publisher,
                state_aggregator=deps.orchestrator.state_aggregator,
                logger=logger,
                shutdown_event=deps.shutdown_event,
            )
        return ModelLoadingResult.failed(
            f"Model '{universal_id}' failed to load on plugin '{plugin_name}'.",
        )
    error_message = (
        f"Timed out loading plugin {plugin_name} after {load_timeout}s."
        if isinstance(exception, asyncio.TimeoutError | SoAITimeoutError)
        else f"Error starting or loading plugin {plugin_name}: {classification.reason}"
    )
    log_exception(
        logger,
        exception,
        message=error_message,
        operation=OPERATION,
    )
    if not is_model_test_request:
        error_published = await publish_model_load_terminal_state_if_current(
            deps,
            plugin_name=plugin_name,
            target_state=ORCH_STATE_ERROR,
            reason=f"Exception during model load: {classification.reason}",
            logger=logger,
        )
        if not error_published:
            await _terminate_model_load_backend(
                deps,
                plugin_name=plugin_name,
                plugin_instance=plugin_instance,
                logger=logger,
                failure_context=failure_context,
            )
            return ModelLoadingResult.deferred()
        try:
            await deps.circuit_breakers.record_cb_failure(plugin_name)
        except RECOVERABLE_EXCEPTIONS as cb_exception:
            log_handled_exception(
                logger,
                cb_exception,
                message="Failed recording circuit breaker failure after model load error (non-critical).",
                operation=OPERATION,
                details={"plugin": plugin_name},
                level="debug",
            )
    await _terminate_model_load_backend(
        deps,
        plugin_name=plugin_name,
        plugin_instance=plugin_instance,
        logger=logger,
        failure_context=failure_context,
    )
    if is_model_test_request:
        await publish_model_load_terminal_state_if_current(
            deps,
            plugin_name=plugin_name,
            target_state=ORCH_STATE_STOPPED,
            reason=f"Model test load failed; plugin stopped. Exception: {classification.reason}",
            logger=logger,
        )
    return ModelLoadingResult.failed(f"Plugin '{plugin_name}' failed during model load.")


async def _terminate_model_load_backend(
    deps: OrchestratorLifecycleModelLoadingDependencies,
    *,
    plugin_name: str,
    plugin_instance: PluginInstanceProtocol | None,
    logger: LoggerProtocol,
    failure_context: str,
) -> bool:
    if plugin_instance is None:
        return True
    if supports_backend_process_tracking(plugin_instance):
        stop_outcome = await perform_tracked_plugin_stop_logic(
            plugin_instance,
            plugin_name=plugin_name,
            database_plugins=deps.orchestrator.database_plugins,
            graceful_budget_sec=0.0,
            logger=logger,
        )
        if not stop_outcome.terminated:
            logger.critical(
                "Failed to stop tracking-enabled plugin '%s' after %s failure.",
                plugin_name,
                failure_context,
            )
        return bool(stop_outcome.terminated)
    terminated = await force_kill_plugin_backend_processes(
        plugin_instance,
        logger=logger,
        missing_pids_is_success=False,
    )
    if not terminated:
        logger.critical(
            "Failed to stop non-tracking plugin '%s' after %s failure.",
            plugin_name,
            failure_context,
        )
    return bool(terminated)

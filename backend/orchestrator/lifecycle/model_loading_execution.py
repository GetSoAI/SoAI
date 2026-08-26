"""SoAI - Model loading execution workflow [backend/orchestrator/lifecycle/model_loading_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAITimeoutError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import publication_completion_deadline
from core.events.types_models_model_events import ModelLoadedEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_base import DIRECTOR_MODEL_LOADS_SUCCESSFUL
from core.runtime.backend_process_tracking import (
    backend_process_identities_to_json_dicts,
)
from core.runtime.backend_process_tracking_db import (
    cleanup_tracked_backend_processes_from_database,
)
from core.runtime.request_context import create_system_context
from core.runtime.request_sources import REQUEST_SOURCE_MODEL_TEST
from core.state.state_names import ORCH_STATE_ERROR
from core.tasks.task import Task
from orchestrator.lifecycle.model_loading_cleanup import (
    publish_cancelled_model_load_terminal_state_if_valid,
    stop_plugin_for_model_load_cleanup,
    stop_started_plugin_for_concurrent_lifecycle_state_change,
)
from orchestrator.lifecycle.model_loading_failure_handling import (
    handle_model_loading_exception,
)
from orchestrator.lifecycle.model_loading_progress_transitions import (
    ensure_starting_state,
    publish_loading_state,
    publish_ready_pending_dispatch_state,
)
from orchestrator.lifecycle.model_loading_result import (
    ModelLoadingResult,
    ModelScopedLoadError,
)
from orchestrator.lifecycle.model_loading_start import start_plugin_process_with_model
from orchestrator.lifecycle.plugin_readiness import wait_for_plugin_ready
from orchestrator.lifecycle.tracked_backend_processes import (
    perform_tracked_plugin_stop_logic,
    supports_backend_process_tracking,
)
from orchestrator.plugin_state import PluginState

if TYPE_CHECKING:
    from core.runtime.backend_process_tracking import BackendProcessIdentity
    from core.types.json import JSONValue
    from orchestrator.lifecycle.model_loading_dependencies import (
        OrchestratorLifecycleModelLoadingDependencies,
    )

    type ModelInfo = Mapping[str, JSONValue]

__all__ = ("execute_start_plugin_and_load_model",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.model_loading_execution"
OPERATION = "orchestrator.start_plugin_and_load_model"
_MODEL_LOAD_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    StateError,
    *RECOVERABLE_EXCEPTIONS,
)


async def execute_start_plugin_and_load_model(
    deps: OrchestratorLifecycleModelLoadingDependencies,
    *,
    adjust_pending_loads: Callable[[int], Awaitable[None]],
    task: Task,
    plugin_name: str,
    model_info: ModelInfo,
    universal_id: str,
    load_timeout: float,
) -> ModelLoadingResult:
    logger = get_logger(LOGGER_NAME)
    plugin_instance = None
    started_process = False
    pending_incremented = False
    is_model_test_request = False
    starting_state_confirmed = False
    try:
        context = task.require_orchestration_context()
        is_model_test_request = context.request_source == REQUEST_SOURCE_MODEL_TEST
        if context.event is None:
            raise StateError("Missing inference event for task during model load.")
        start_with_lock = deps.orchestrator.plugin_manager.lifecycle.plugin_lock_scope(plugin_name)
        supports_process_tracking = False
        persisted_identities: list[BackendProcessIdentity] = []
        plugin_instance_value = None
        async with start_with_lock:
            plugin_instance_value = await deps.orchestrator.plugin_manager.require_loaded_plugin(
                plugin_name,
                auto_load=True,
            )
            if not await ensure_starting_state(
                plugin_name=plugin_name,
                universal_id=universal_id,
                publisher=deps.lifecycle_publisher,
                state_aggregator=deps.orchestrator.state_aggregator,
                logger=logger,
            ):
                return ModelLoadingResult.deferred()
            starting_state_confirmed = True
            await uncancel_then_cleanup(adjust_pending_loads(1))
            pending_incremented = True
            plugin_instance = plugin_instance_value
            supports_process_tracking = supports_backend_process_tracking(plugin_instance_value)
            if supports_process_tracking:
                cleanup_result = await cleanup_tracked_backend_processes_from_database(
                    deps.orchestrator.database_plugins,
                    plugin_name=plugin_name,
                    logger=logger,
                )
                if cleanup_result is not None and (not cleanup_result.succeeded):
                    to_json_identities = backend_process_identities_to_json_dicts
                    receipt = await deps.lifecycle_publisher.publish_runtime_state_change(
                        plugin_name,
                        ORCH_STATE_ERROR,
                        "Refusing to start: existing tracked backend process cleanup failed.",
                        details={
                            "killed": to_json_identities(cleanup_result.killed),
                            "mismatched": to_json_identities(cleanup_result.mismatched),
                            "already_gone": to_json_identities(cleanup_result.already_gone),
                            "failed": to_json_identities(cleanup_result.failed),
                        },
                    )
                    if receipt is not None:
                        await receipt.wait_for_completion(publication_completion_deadline())
                    return ModelLoadingResult.failed(
                        "Existing tracked backend process cleanup failed before model load.",
                    )
            start_success, supports_process_tracking, persisted_identities = (
                await start_plugin_process_with_model(
                    plugin_instance_value,
                    plugin_name=plugin_name,
                    task=task,
                    model_info=model_info,
                    request_context=context.event.context,
                    database_plugins=deps.orchestrator.database_plugins,
                    load_timeout=load_timeout,
                    logger=logger,
                )
            )
            started_process = bool(start_success)
            if not start_success:
                raise ModelScopedLoadError(
                    f"Plugin '{plugin_name}' failed to start process for model '{universal_id}'.",
                )
            if supports_process_tracking and (not persisted_identities):
                stop_outcome = await perform_tracked_plugin_stop_logic(
                    plugin_instance_value,
                    plugin_name=plugin_name,
                    database_plugins=deps.orchestrator.database_plugins,
                    graceful_budget_sec=0.0,
                    logger=logger,
                )
                if not stop_outcome.terminated:
                    logger.critical(
                        "Tracked cleanup failed after plugin '%s' reported no backend PIDs.",
                        plugin_name,
                    )
                receipt = await deps.lifecycle_publisher.publish_runtime_state_change(
                    plugin_name,
                    ORCH_STATE_ERROR,
                    "Plugin contract violation: SUPPORTS_BACKEND_PROCESS_TRACKING=True but no backend PIDs were reported after start_with_model().",
                )
                if receipt is not None:
                    await receipt.wait_for_completion(publication_completion_deadline())
                return ModelLoadingResult.failed(
                    "Plugin contract violation: backend process tracking reported no PIDs.",
                )
            if not await publish_loading_state(
                plugin_name=plugin_name,
                universal_id=universal_id,
                publisher=deps.lifecycle_publisher,
                logger=logger,
            ):
                await stop_started_plugin_for_concurrent_lifecycle_state_change(
                    deps,
                    started_process=True,
                    plugin_instance=plugin_instance_value,
                    plugin_name=plugin_name,
                    logger=logger,
                )
                started_process = False
                return ModelLoadingResult.deferred()
        if plugin_instance_value is None:
            raise StateError("Missing plugin instance after start process.")
        if not await wait_for_plugin_ready(
            plugin_instance_value,
            deps.shutdown_event,
            load_timeout,
            require_live_backend_process=supports_process_tracking,
        ):
            raise SoAITimeoutError(
                f"Plugin '{plugin_name}' did not become healthy within {load_timeout}s.",
            )
        loaded_parameters = dict(context.startup_params)
        parameter_version = (
            context.parameter_version if context.parameter_version is not None else 0
        )
        if not await publish_ready_pending_dispatch_state(
            plugin_name=plugin_name,
            universal_id=universal_id,
            publisher=deps.lifecycle_publisher,
            logger=logger,
        ):
            await stop_started_plugin_for_concurrent_lifecycle_state_change(
                deps,
                started_process=started_process,
                plugin_instance=plugin_instance,
                plugin_name=plugin_name,
                logger=logger,
            )
            return ModelLoadingResult.deferred()
        async with deps.state.plugins_context() as plugin_context:
            plugin_state = plugin_context.plugin_states.get(plugin_name)
            if plugin_state is None:
                plugin_state = PluginState(plugin_name=plugin_name)
                plugin_context.plugin_states[plugin_name] = plugin_state
            plugin_state.loaded_model_universal_id = universal_id
            plugin_state.last_activity = time.monotonic()
            plugin_state.model_load_time = time.monotonic()
            plugin_state.loaded_parameters = loaded_parameters
            plugin_state.parameter_version = parameter_version
        await deps.orchestrator.bus.publish(
            ModelLoadedEvent(
                context=create_system_context("model_load"),
                plugin_name=plugin_name,
                universal_id=universal_id,
            ),
        )
        deps.orchestrator.metrics.increment_counter(*DIRECTOR_MODEL_LOADS_SUCCESSFUL)
        return ModelLoadingResult.success()
    except asyncio.CancelledError:
        if starting_state_confirmed:
            if plugin_instance is not None:
                await uncancel_then_cleanup(
                    stop_plugin_for_model_load_cleanup(
                        plugin_instance=plugin_instance,
                        plugin_name=plugin_name,
                        database_plugins=deps.orchestrator.database_plugins,
                        publisher=deps.lifecycle_publisher,
                        state_aggregator=deps.orchestrator.state_aggregator,
                        reason="Model load cancelled; stopping plugin.",
                        publish_state_changes=not deps.shutdown_event.is_set(),
                        logger=logger,
                        shutdown_event=deps.shutdown_event,
                    ),
                )
            else:
                if not deps.shutdown_event.is_set():
                    await uncancel_then_cleanup(
                        publish_cancelled_model_load_terminal_state_if_valid(
                            plugin_name=plugin_name,
                            publisher=deps.lifecycle_publisher,
                            state_aggregator=deps.orchestrator.state_aggregator,
                            reason="Model load cancelled; returning to STOPPED.",
                            logger=logger,
                            shutdown_event=deps.shutdown_event,
                        ),
                    )
        raise
    except _MODEL_LOAD_FAILURE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Model loading execution failed.",
            operation=OPERATION,
            details={"plugin_name": plugin_name, "task_id": task.task_id},
            level="warning",
        )
        return await handle_model_loading_exception(
            deps,
            plugin_name=plugin_name,
            universal_id=universal_id,
            load_timeout=load_timeout,
            exception=exception,
            logger=logger,
            started_process=started_process,
            plugin_instance=plugin_instance,
            is_model_test_request=is_model_test_request,
        )
    finally:
        if pending_incremented:
            await uncancel_then_cleanup(adjust_pending_loads(-1))

"""SoAI - Dispatch runtime instance invariant checks [backend/orchestrator/scheduling/dispatch_runtime_invariant.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import await_publication_receipt
from core.state.state_names import ORCH_STATE_ERROR
from orchestrator.lifecycle.state_transition_validation import (
    is_invalid_transition_error,
)
from orchestrator.scheduling.plugin_action_failure import PluginActionFailure

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.plugins.protocols import PluginManagerProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.protocols import AuthoritativePluginStateTransitionReceipt
    from core.state.state_names import PluginRuntimeStateName
    from orchestrator.scheduling.internal_protocols import (
        DispatchRuntimeInvariantDependenciesProtocol,
    )

__all__ = (
    "DispatchRuntimeInvariantResult",
    "ensure_dispatch_runtime_instance",
    "ensure_scheduler_dispatch_runtime_instance",
)

INVARIANT_REASON = "Dispatch-ready plugin is missing its runtime instance."
OPERATION = "orchestrator.scheduler.dispatch_runtime_invariant"


@dataclass(frozen=True, slots=True)
class DispatchRuntimeInvariantResult:
    outcome: Literal["available", "state_changed", "missing"]
    plugin_instance: PluginInstanceProtocol | None = None
    failure: PluginActionFailure | None = None
    plugin_status: str | None = None


async def ensure_dispatch_runtime_instance(
    *,
    plugin_name: str,
    provider_backed: bool,
    plugin_manager: PluginManagerProtocol,
    state_aggregator_get_status: Callable[[str], Awaitable[PluginRuntimeStateName]],
    lifecycle_publish_state_change: Callable[
        [str, PluginRuntimeStateName, str],
        Awaitable[AuthoritativePluginStateTransitionReceipt | None],
    ],
    dispatch_ready_states: set[str],
    logger: TraceLogger,
) -> DispatchRuntimeInvariantResult:
    if provider_backed:
        return DispatchRuntimeInvariantResult(outcome="available")
    plugin_instance = await plugin_manager.get_plugin_instance(plugin_name)
    if plugin_instance is not None:
        return DispatchRuntimeInvariantResult(
            outcome="available",
            plugin_instance=plugin_instance,
        )
    plugin_status = await state_aggregator_get_status(plugin_name)
    if plugin_status not in dispatch_ready_states:
        return DispatchRuntimeInvariantResult(
            outcome="state_changed",
            plugin_status=plugin_status,
        )
    try:
        hydrated_instance = await plugin_manager.require_loaded_plugin(
            plugin_name,
            auto_load=True,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        current_status = await state_aggregator_get_status(plugin_name)
        if current_status not in dispatch_ready_states:
            return DispatchRuntimeInvariantResult(
                outcome="state_changed",
                plugin_status=current_status,
            )
        log_exception(
            logger,
            exception,
            message="Failed to hydrate dispatch-ready plugin runtime surface.",
            operation=OPERATION,
            details={"plugin": plugin_name},
            level="warning",
        )
    else:
        current_status = await state_aggregator_get_status(plugin_name)
        if current_status not in dispatch_ready_states:
            return DispatchRuntimeInvariantResult(
                outcome="state_changed",
                plugin_status=current_status,
            )
        return DispatchRuntimeInvariantResult(
            outcome="available",
            plugin_instance=hydrated_instance,
            plugin_status=current_status,
        )
    try:
        receipt = await lifecycle_publish_state_change(
            plugin_name,
            ORCH_STATE_ERROR,
            INVARIANT_REASON,
        )
        await await_publication_receipt(receipt)
    except RECOVERABLE_EXCEPTIONS as exception:
        if is_invalid_transition_error(exception):
            logger.debug(
                "Skipping runtime-instance invariant publication for '%s' because state changed concurrently.",
                plugin_name,
            )
            return DispatchRuntimeInvariantResult(
                outcome="state_changed",
                plugin_status=await state_aggregator_get_status(plugin_name),
            )
        log_exception(
            logger,
            exception,
            message="Failed to publish runtime-instance invariant failure.",
            operation=OPERATION,
            details={"plugin": plugin_name},
            level="warning",
        )
        raise
    failure = PluginActionFailure(
        message="The model backend is recovering from a runtime state mismatch. Please retry in a few seconds.",
        operator_reason=f"Plugin '{plugin_name}' was dispatch-ready without a runtime instance.",
        error_type=ErrorType.PLUGIN_UNAVAILABLE,
    )
    return DispatchRuntimeInvariantResult(
        outcome="missing",
        failure=failure,
        plugin_status=ORCH_STATE_ERROR,
    )


async def ensure_scheduler_dispatch_runtime_instance(
    *,
    deps: DispatchRuntimeInvariantDependenciesProtocol,
    plugin_name: str,
    provider_backed: bool,
    logger: TraceLogger,
) -> DispatchRuntimeInvariantResult:
    lifecycle = deps.lifecycle
    publisher = lifecycle.publisher

    return await ensure_dispatch_runtime_instance(
        plugin_name=plugin_name,
        provider_backed=provider_backed,
        plugin_manager=deps.plugin_manager,
        state_aggregator_get_status=deps.state_aggregator.get_plugin_status,
        lifecycle_publish_state_change=publisher.publish_runtime_state_change,
        dispatch_ready_states=deps.dispatch_ready_states,
        logger=logger,
    )

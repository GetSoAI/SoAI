"""SoAI - Model loading terminal cleanup state transitions [backend/orchestrator/lifecycle/model_loading_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.plugins.persistent_runtime_truth import resolve_persistent_runtime_state
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
    PLUGIN_STATE_PERSISTENT_READY,
    PluginRuntimeStateName,
)
from core.state.state_transition_graph import get_valid_state_transitions
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)
from orchestrator.lifecycle.state_transition_validation import (
    is_invalid_transition_error,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorLifecyclePublisherProtocol,
    )
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.protocols import StateAggregatorProtocol

__all__ = (
    "publish_model_load_stopped_terminal_state_if_valid",
    "publish_stopping_if_valid",
    "publish_terminal_state_if_valid",
)

OPERATION_MODEL_LOADING = "orchestrator.start_plugin_and_load_model"


async def publish_stopping_if_valid(
    *,
    plugin_name: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    reason: str,
    logger: LoggerProtocol,
) -> bool:
    try:
        current_status = await state_aggregator.get_plugin_status(plugin_name)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed reading plugin state before STOPPING publish (non-critical).",
            operation=OPERATION_MODEL_LOADING,
            details={"plugin": plugin_name},
            level="debug",
        )
        return False
    if current_status == ORCH_STATE_STOPPING:
        return False
    valid_transitions: tuple[PluginRuntimeStateName, ...] = get_valid_state_transitions(
        current_status,
    )
    if ORCH_STATE_STOPPING not in valid_transitions:
        return False
    try:
        return await publish_runtime_state_change_and_wait(
            publisher=publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_STOPPING,
            reason=reason,
            expected_previous_state=current_status,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if is_invalid_transition_error(exception):
            return False
        log_handled_exception(
            logger,
            exception,
            message="Failed publishing STOPPING state during model load cleanup (non-critical).",
            operation=OPERATION_MODEL_LOADING,
            details={"plugin": plugin_name},
            level="debug",
        )
        return False


async def publish_terminal_state_if_valid(
    *,
    plugin_name: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    new_state: PluginRuntimeStateName,
    reason: str,
    logger: LoggerProtocol,
    previous_state_override: PluginRuntimeStateName | None = None,
) -> bool:
    current_status = previous_state_override
    if current_status is None:
        try:
            current_status = await state_aggregator.get_plugin_status(plugin_name)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed reading plugin state before terminal publish (non-critical).",
                operation=OPERATION_MODEL_LOADING,
                details={"plugin": plugin_name},
                level="debug",
            )
            return False
    if current_status == new_state:
        return False
    if current_status == ORCH_STATE_STOPPING and new_state == PLUGIN_STATE_PERSISTENT_READY:
        return await _publish_stopping_to_persistent_ready(
            plugin_name=plugin_name,
            publisher=publisher,
            reason=reason,
            logger=logger,
        )
    valid_transitions: tuple[PluginRuntimeStateName, ...] = get_valid_state_transitions(
        current_status,
    )
    if new_state not in valid_transitions:
        logger.debug(
            "Skipping terminal state publish for '%s': %s -> %s is not a valid transition.",
            plugin_name,
            current_status,
            new_state,
        )
        return False
    try:
        return await publish_runtime_state_change_and_wait(
            publisher=publisher,
            plugin_name=plugin_name,
            new_state=new_state,
            reason=reason,
            expected_previous_state=current_status,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if is_invalid_transition_error(exception):
            return False
        log_handled_exception(
            logger,
            exception,
            message="Failed publishing terminal state during model load cleanup (non-critical).",
            operation=OPERATION_MODEL_LOADING,
            details={"plugin": plugin_name},
            level="debug",
        )
        return False


async def _publish_stopping_to_persistent_ready(
    *,
    plugin_name: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    reason: str,
    logger: LoggerProtocol,
) -> bool:
    try:
        stopped_published = await publish_runtime_state_change_and_wait(
            publisher=publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_STOPPED,
            reason="Plugin state returned to STOPPED before persistent readiness.",
            expected_previous_state=ORCH_STATE_STOPPING,
        )
        if not stopped_published:
            return False
        persistent_ready_published = await publish_runtime_state_change_and_wait(
            publisher=publisher,
            plugin_name=plugin_name,
            new_state=PLUGIN_STATE_PERSISTENT_READY,
            reason=reason,
            expected_previous_state=ORCH_STATE_STOPPED,
        )
        return persistent_ready_published
    except RECOVERABLE_EXCEPTIONS as exception:
        if is_invalid_transition_error(exception):
            return False
        log_handled_exception(
            logger,
            exception,
            message="Failed publishing persistent-ready terminal bridge during model load cleanup (non-critical).",
            operation=OPERATION_MODEL_LOADING,
            details={"plugin": plugin_name},
            level="debug",
        )
        return False


async def publish_model_load_stopped_terminal_state_if_valid(
    *,
    plugin_instance: PluginInstanceProtocol,
    terminated: bool,
    stopped_reason: str,
    failed_reason: str,
    operation: str,
    plugin_name: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    logger: LoggerProtocol,
    previous_state_override: PluginRuntimeStateName | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    if shutdown_event is not None and shutdown_event.is_set():
        return
    if not terminated:
        await publish_terminal_state_if_valid(
            plugin_name=plugin_name,
            publisher=publisher,
            state_aggregator=state_aggregator,
            new_state=ORCH_STATE_ERROR,
            reason=failed_reason,
            logger=logger,
            previous_state_override=previous_state_override,
        )
        return
    stopped_published = await publish_terminal_state_if_valid(
        plugin_name=plugin_name,
        publisher=publisher,
        state_aggregator=state_aggregator,
        new_state=ORCH_STATE_STOPPED,
        reason=stopped_reason,
        logger=logger,
        previous_state_override=previous_state_override,
    )
    if not stopped_published or not plugin_instance.PERSISTENT:
        return
    if shutdown_event is not None and shutdown_event.is_set():
        return
    target_state, persistent_reason, _ = await resolve_persistent_runtime_state(
        plugin_instance,
        attempt_activate=True,
        failure_state=ORCH_STATE_ERROR,
        operation=operation,
        logger=logger,
    )
    if shutdown_event is not None and shutdown_event.is_set():
        return
    await publish_terminal_state_if_valid(
        plugin_name=plugin_name,
        publisher=publisher,
        state_aggregator=state_aggregator,
        new_state=target_state,
        reason=f"{stopped_reason} {persistent_reason}".strip(),
        logger=logger,
    )

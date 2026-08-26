"""SoAI - Model loading progress state transitions [backend/orchestrator/lifecycle/model_loading_progress_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_LOADING,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_READY_PENDING_DISPATCH,
    ORCH_STATE_STARTING,
    ORCH_STATE_STOPPED,
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_PERSISTENT_READY,
)
from core.state.state_transition_graph import get_valid_state_transitions
from orchestrator.lifecycle.model_loading_cleanup import (
    publish_cancelled_model_load_terminal_state_if_valid,
)
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
    from core.state.protocols import StateAggregatorProtocol

__all__ = (
    "ensure_starting_state",
    "publish_loading_state",
    "publish_ready_pending_dispatch_state",
)

OPERATION_MODEL_LOADING = "orchestrator.start_plugin_and_load_model"
_MODEL_LOAD_TERMINAL_UNAVAILABLE_STATES = (
    ORCH_STATE_DISABLED,
    ORCH_STATE_QUARANTINED,
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_NOT_DETECTED,
)


async def ensure_starting_state(
    *,
    plugin_name: str,
    universal_id: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    logger: LoggerProtocol,
) -> bool:
    current_status = await state_aggregator.get_plugin_status(plugin_name)
    terminal_state = (
        PLUGIN_STATE_PERSISTENT_READY
        if current_status == PLUGIN_STATE_PERSISTENT_READY
        else ORCH_STATE_STOPPED
    )
    terminal_reason = (
        "Model load cancelled; persistent plugin returned to PERSISTENT_READY."
        if current_status == PLUGIN_STATE_PERSISTENT_READY
        else "Model load cancelled; plugin returned to STOPPED."
    )
    if current_status == ORCH_STATE_STARTING:
        return True
    valid_transitions = get_valid_state_transitions(current_status)
    if ORCH_STATE_STARTING not in valid_transitions:
        if current_status.endswith("_ERROR") or current_status in (
            _MODEL_LOAD_TERMINAL_UNAVAILABLE_STATES
        ):
            raise StateError(f"Plugin '{plugin_name}' is unavailable for model loading.")
        logger.info(
            "Aborting model load for '%s'. Current state '%s' cannot transition to STARTING.",
            plugin_name,
            current_status,
        )
        return False
    try:
        try:
            await publish_runtime_state_change_and_wait(
                publisher=publisher,
                plugin_name=plugin_name,
                new_state=ORCH_STATE_STARTING,
                reason=f"Starting plugin for model {universal_id}",
                details={"universal_id": universal_id},
            )
        except asyncio.CancelledError:
            await uncancel_then_cleanup(
                publish_cancelled_model_load_terminal_state_if_valid(
                    plugin_name=plugin_name,
                    publisher=publisher,
                    state_aggregator=state_aggregator,
                    logger=logger,
                    reason="Model load cancelled during STARTING.",
                    terminal_state=terminal_state,
                    terminal_reason=terminal_reason,
                ),
            )
            raise
        return True
    except RECOVERABLE_EXCEPTIONS as exception:
        if is_invalid_transition_error(exception):
            logger.info(
                "Aborting model load for '%s': STARTING transition rejected (concurrent lifecycle change).",
                plugin_name,
            )
            return False
        raise


async def publish_loading_state(
    *,
    plugin_name: str,
    universal_id: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    logger: LoggerProtocol,
) -> bool:
    try:
        await publish_runtime_state_change_and_wait(
            publisher=publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_LOADING,
            reason=f"Loading model {universal_id}",
            details={"universal_id": universal_id},
        )
        return True
    except RECOVERABLE_EXCEPTIONS as exception:
        if is_invalid_transition_error(exception):
            log_exception(
                logger,
                exception,
                message="Aborting model load: LOADING transition rejected (concurrent lifecycle change).",
                operation=OPERATION_MODEL_LOADING,
                details={"plugin": plugin_name},
                level="warning",
            )
            return False
        raise


async def publish_ready_pending_dispatch_state(
    *,
    plugin_name: str,
    universal_id: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    logger: LoggerProtocol,
) -> bool:
    try:
        await publish_runtime_state_change_and_wait(
            publisher=publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_READY_PENDING_DISPATCH,
            reason="Model loaded, awaiting dispatch",
            details={"universal_id": universal_id},
        )
        return True
    except RECOVERABLE_EXCEPTIONS as exception:
        if is_invalid_transition_error(exception):
            log_exception(
                logger,
                exception,
                message="Aborting model load: READY_PENDING_DISPATCH transition rejected (concurrent lifecycle change).",
                operation=OPERATION_MODEL_LOADING,
                details={"plugin": plugin_name},
                level="warning",
            )
            return False
        raise

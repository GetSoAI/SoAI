"""SoAI - Model loading failure state publication [backend/orchestrator/lifecycle/model_loading_failure_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.state.state_names import ORCH_STATE_STOPPED, ORCH_STATE_STOPPING
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)
from orchestrator.lifecycle.state_transition_validation import (
    is_invalid_transition_error,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.state.state_names import PluginRuntimeStateName
    from orchestrator.lifecycle.model_loading_dependencies import (
        OrchestratorLifecycleModelLoadingDependencies,
    )

__all__ = ("publish_model_load_terminal_state_if_current",)

OPERATION = "orchestrator.start_plugin_and_load_model"


async def publish_model_load_terminal_state_if_current(
    deps: OrchestratorLifecycleModelLoadingDependencies,
    *,
    plugin_name: str,
    target_state: PluginRuntimeStateName,
    reason: str,
    logger: LoggerProtocol,
) -> bool:
    if deps.shutdown_event.is_set():
        return False
    try:
        current_status = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
    except RECOVERABLE_EXCEPTIONS as state_exception:
        log_handled_exception(
            logger,
            state_exception,
            message="Skipping model-load terminal publish: current state unavailable (non-critical).",
            operation=OPERATION,
            details={"plugin": plugin_name, "target_state": target_state},
            level="debug",
        )
        return False
    if deps.shutdown_event.is_set() or current_status in {
        ORCH_STATE_STOPPING,
        ORCH_STATE_STOPPED,
    }:
        logger.debug(
            "Skipping model-load terminal publish for '%s': shutdown or another lifecycle operation owns state '%s'.",
            plugin_name,
            current_status,
        )
        return False
    try:
        published = await publish_runtime_state_change_and_wait(
            publisher=deps.lifecycle_publisher,
            plugin_name=plugin_name,
            new_state=target_state,
            reason=reason,
            expected_previous_state=current_status,
        )
        if not published:
            logger.debug(
                "Skipping model-load terminal publish for '%s': concurrent lifecycle change superseded it.",
                plugin_name,
            )
            return False
        return True
    except RECOVERABLE_EXCEPTIONS as publish_exception:
        if is_invalid_transition_error(publish_exception):
            log_handled_exception(
                logger,
                publish_exception,
                message="Skipping model-load terminal publish: transition rejected (non-critical).",
                operation=OPERATION,
                details={"plugin": plugin_name, "target_state": target_state},
                level="debug",
            )
            return False
        raise

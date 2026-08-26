"""SoAI - Persistent plugin config reload recovery [backend/orchestrator/lifecycle/plugin_config_reload_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.protocols import LoggerProtocol
from core.orchestrator.protocols_lifecycle import OrchestratorLifecyclePublisherProtocol
from core.plugins.persistent_runtime_truth import resolve_persistent_runtime_state
from core.plugins.protocols import PluginManagerProtocol
from core.state.state_names import ORCH_STATE_ERROR, PLUGIN_STATE_PERSISTENT_READY
from orchestrator.lifecycle.config_reload_result import (
    PluginConfigReloadOutcome,
    PluginConfigReloadResult,
)
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)

__all__ = ("restore_persistent_ready_after_config_reload",)


async def restore_persistent_ready_after_config_reload(
    *,
    plugin_name: str,
    prior_status: str,
    plugin_manager: PluginManagerProtocol,
    lifecycle_publisher: OrchestratorLifecyclePublisherProtocol,
    logger: LoggerProtocol,
) -> PluginConfigReloadResult | None:
    if prior_status != PLUGIN_STATE_PERSISTENT_READY:
        return None
    instance = await plugin_manager.get_plugin_instance(plugin_name)
    if instance is None or not instance.PERSISTENT:
        error = "persistent plugin instance unavailable after config reload"
        await publish_runtime_state_change_and_wait(
            publisher=lifecycle_publisher,
            plugin_name=plugin_name,
            new_state=ORCH_STATE_ERROR,
            reason=error,
        )
        return PluginConfigReloadResult(
            PluginConfigReloadOutcome.FAILED_RETRYABLE,
            error=error,
        )
    target_state, reason, _ = await resolve_persistent_runtime_state(
        instance,
        attempt_activate=True,
        failure_state=ORCH_STATE_ERROR,
        operation="orchestrator.lifecycle.plugin_config_reload.persistent",
        logger=logger,
    )
    await publish_runtime_state_change_and_wait(
        publisher=lifecycle_publisher,
        plugin_name=plugin_name,
        new_state=target_state,
        reason=f"Config reload applied. {reason}",
    )
    if target_state != PLUGIN_STATE_PERSISTENT_READY:
        return PluginConfigReloadResult(
            PluginConfigReloadOutcome.FAILED_RETRYABLE,
            error=reason,
        )
    return None

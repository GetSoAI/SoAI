"""SoAI - Runtime state transition publication [backend/orchestrator/lifecycle/state_transition_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.completion_waiting import await_publication_receipt

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorLifecyclePublisherProtocol,
    )
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict

__all__ = ("publish_runtime_state_change_and_wait",)


async def publish_runtime_state_change_and_wait(
    *,
    publisher: OrchestratorLifecyclePublisherProtocol,
    plugin_name: str,
    new_state: PluginRuntimeStateName,
    reason: str,
    details: JSONDict | None = None,
    expected_previous_state: PluginRuntimeStateName | None = None,
) -> bool:
    if details is None and expected_previous_state is None:
        receipt = await publisher.publish_runtime_state_change(plugin_name, new_state, reason)
    elif details is None:
        receipt = await publisher.publish_runtime_state_change(
            plugin_name,
            new_state,
            reason,
            expected_previous_state=expected_previous_state,
        )
    elif expected_previous_state is None:
        receipt = await publisher.publish_runtime_state_change(
            plugin_name,
            new_state,
            reason,
            details=details,
        )
    else:
        receipt = await publisher.publish_runtime_state_change(
            plugin_name,
            new_state,
            reason,
            details=details,
            expected_previous_state=expected_previous_state,
        )
    if receipt is None:
        return False
    await await_publication_receipt(receipt)
    return True

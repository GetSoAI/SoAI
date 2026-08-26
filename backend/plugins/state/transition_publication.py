"""SoAI - Plugin transition and publication helpers [backend/plugins/state/transition_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from plugins.state.publication_wait import wait_for_plugin_state_publication

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.state.state_names import PluginRuntimeStateName
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("transition_plugin_state_and_wait",)


async def transition_plugin_state_and_wait(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    new_state: PluginRuntimeStateName,
    reason: str,
    context: RequestContext | None = None,
    *,
    completion_deadline_monotonic: float | None = None,
) -> None:
    receipt = await manager.transition_plugin_manager_state(
        plugin_name,
        new_state,
        reason,
        context,
    )
    if completion_deadline_monotonic is None:
        await wait_for_plugin_state_publication(receipt)
    elif receipt is not None:
        await receipt.wait_for_completion(completion_deadline_monotonic)

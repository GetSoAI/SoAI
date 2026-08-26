"""SoAI - Plugin state publication completion waits [backend/plugins/state/publication_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.events.completion_waiting import await_publication_receipt

if TYPE_CHECKING:
    from core.state.protocols import AuthoritativePluginStateTransitionReceipt

__all__ = ("wait_for_plugin_state_publication",)


async def wait_for_plugin_state_publication(
    receipt: AuthoritativePluginStateTransitionReceipt | None,
) -> None:
    await await_publication_receipt(receipt)

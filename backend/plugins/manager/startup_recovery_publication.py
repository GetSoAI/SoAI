"""SoAI - Startup recovery publication waits [backend/plugins/manager/startup_recovery_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.completion_waiting import await_publication_receipt
from core.state.protocols import AuthoritativePluginStateTransitionReceipt

__all__ = ("wait_for_startup_recovery_publication",)


async def wait_for_startup_recovery_publication(
    receipt: AuthoritativePluginStateTransitionReceipt | None,
) -> None:
    await await_publication_receipt(receipt)

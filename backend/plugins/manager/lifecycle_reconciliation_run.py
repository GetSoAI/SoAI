"""SoAI - Plugin manager reconciliation run ownership [backend/plugins/manager/lifecycle_reconciliation_run.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = (
    "claim_initial_reconciliation_run",
    "clear_initial_reconciliation_run",
)


async def claim_initial_reconciliation_run(
    manager: PluginManagerLifecycleTarget,
) -> asyncio.Task[None] | None:
    current_task = asyncio.current_task()
    async with manager.state.lifecycle.reconciliation_start_lock:
        ongoing_task = manager.state.lifecycle.reconciliation_task
        if ongoing_task and ongoing_task is not current_task and (not ongoing_task.done()):
            async with manager.state.lifecycle.reconciliation_pending_lock:
                manager.state.lifecycle.reconciliation_pending = True
            return ongoing_task
        if current_task is not None:
            manager.state.lifecycle.reconciliation_task = current_task
        return None


def clear_initial_reconciliation_run(manager: PluginManagerLifecycleTarget) -> None:
    current_task = asyncio.current_task()
    if manager.state.lifecycle.reconciliation_task is current_task:
        manager.state.lifecycle.reconciliation_task = None

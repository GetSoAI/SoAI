"""SoAI - Plugin manager reconciliation completion waiting [backend/plugins/manager/lifecycle_reconciliation_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.logging.trace import get_logger

if TYPE_CHECKING:
    from plugins.manager.internal_protocols import PluginManagerLifecycleTarget

__all__ = ("wait_for_initial_reconciliation_complete",)

LOGGER_NAME = "SoAI.plugins.manager.lifecycle_reconciliation_wait"


async def wait_for_initial_reconciliation_complete(
    manager: PluginManagerLifecycleTarget,
    timeout: float | None = None,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    if manager.state.lifecycle.initial_reconciliation_complete.is_set():
        return True
    try:
        if timeout is None:
            await manager.state.lifecycle.initial_reconciliation_complete.wait()
            return True
        await asyncio.wait_for(
            manager.state.lifecycle.initial_reconciliation_complete.wait(),
            timeout=timeout,
        )
        return True
    except TimeoutError:
        logger.warning("Timed out waiting for plugin reconciliation to complete.")
        return False

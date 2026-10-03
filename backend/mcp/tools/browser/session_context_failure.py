"""SoAI - Browser session context failure cleanup [backend/mcp/tools/browser/session_context_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.timing.constants import CONTROL_TIMEOUT_SEC
from mcp.tools.browser.session_store_lifecycle import close_browser_context
from mcp.tools.browser.types import BrowserSessionState

__all__ = ("close_failed_context_initialization",)


async def close_failed_context_initialization(
    state: BrowserSessionState,
    *,
    operation: str,
) -> None:
    await uncancel_then_cleanup(
        asyncio.wait_for(
            close_browser_context(state, operation=operation),
            timeout=CONTROL_TIMEOUT_SEC,
        ),
    )

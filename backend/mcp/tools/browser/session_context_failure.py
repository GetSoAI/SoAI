"""SoAI - Browser session context failure cleanup [backend/mcp/tools/browser/session_context_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from mcp.tools.browser.session_store_lifecycle import close_browser_context
from mcp.tools.browser.types import BrowserSessionState

__all__ = ("close_failed_context_initialization",)


async def close_failed_context_initialization(
    state: BrowserSessionState,
    *,
    operation: str,
) -> None:
    await asyncio.shield(close_browser_context(state, operation=operation))

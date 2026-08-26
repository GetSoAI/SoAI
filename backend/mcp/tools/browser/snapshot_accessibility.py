"""SoAI - Browser snapshot accessibility fallback helpers [backend/mcp/tools/browser/snapshot_accessibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwright.async_api import Error

if TYPE_CHECKING:
    from playwright.async_api._generated import Page

__all__ = (
    "MainFrameSnapshotTransientError",
    "capture_accessibility_snapshot_text",
)


class MainFrameSnapshotTransientError(Exception): ...


async def capture_accessibility_snapshot_text(
    page: Page,
    *,
    action_timeout_sec: float,
) -> str | None:
    try:
        async with asyncio.timeout(max(0.5, float(action_timeout_sec))):
            locator_timeout_ms = max(500.0, float(action_timeout_sec) * 1000.0)
            locator = page.locator("body")
            return await locator.aria_snapshot(timeout=locator_timeout_ms)
    except (AttributeError, Error, TimeoutError):
        return None

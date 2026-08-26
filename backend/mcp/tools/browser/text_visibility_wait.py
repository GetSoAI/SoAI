"""SoAI - Browser wait-for text primitives [backend/mcp/tools/browser/text_visibility_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from core.types.json import JSONDict

__all__ = (
    "wait_for_any_text_visible",
    "wait_for_text_hidden",
)


async def wait_for_any_text_visible(
    page: Page,
    *,
    text: str,
    timeout_ms: int,
) -> JSONDict:
    start = time.monotonic()
    timeout_sec = float(timeout_ms) / 1000.0
    deadline = start + timeout_sec
    locator: Locator = page.get_by_text(text)
    last_match_count = 0
    last_visible_count = 0
    last_first_visible: bool | None = None
    while True:
        match_count = await locator.count()
        last_match_count = int(match_count)
        visible_count = 0
        first_visible: bool | None = None
        for index in range(match_count):
            candidate = locator.nth(index)
            is_visible = await candidate.is_visible()
            if index == 0:
                first_visible = bool(is_visible)
            if is_visible:
                visible_count += 1
                return {
                    "matched_text": text,
                    "match_count": int(match_count),
                    "visible_match_count": int(visible_count),
                    "matched_any_visible": True,
                }
        last_visible_count = int(visible_count)
        last_first_visible = first_visible
        if time.monotonic() >= deadline:
            raise MCPToolError(
                -32603,
                f"Timeout {timeout_ms}ms exceeded waiting for text to be visible: '{text}'",
                {
                    "match_count": last_match_count,
                    "visible_match_count": last_visible_count,
                    "first_match_visible": last_first_visible,
                },
            )
        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)


async def wait_for_text_hidden(
    page: Page,
    *,
    text: str,
    timeout_ms: int,
) -> JSONDict:
    start = time.monotonic()
    timeout_sec = float(timeout_ms) / 1000.0
    deadline = start + timeout_sec
    locator: Locator = page.get_by_text(text)
    last_match_count = 0
    last_visible_count = 0
    last_first_visible: bool | None = None
    while True:
        match_count = await locator.count()
        last_match_count = int(match_count)
        visible_count = 0
        first_visible: bool | None = None
        for index in range(match_count):
            candidate = locator.nth(index)
            is_visible = await candidate.is_visible()
            if index == 0:
                first_visible = bool(is_visible)
            if is_visible:
                visible_count += 1
        last_visible_count = int(visible_count)
        last_first_visible = first_visible
        if visible_count == 0:
            return {
                "matched_text_gone": text,
                "match_count": int(match_count),
                "visible_match_count": int(visible_count),
                "matched_any_visible": False,
            }
        if time.monotonic() >= deadline:
            raise MCPToolError(
                -32603,
                f"Timeout {timeout_ms}ms exceeded waiting for text to be hidden: '{text}'",
                {
                    "match_count": last_match_count,
                    "visible_match_count": last_visible_count,
                    "first_match_visible": last_first_visible,
                },
            )
        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)

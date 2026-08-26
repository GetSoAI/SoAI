"""SoAI - Agent turn loop retry waiting [backend/features/agent/runtime/turn_loop_retry_wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

__all__ = ("wait_turn_retry_delay",)

_RETRY_WAIT_CANCEL_POLL_SECONDS = 0.1


async def wait_turn_retry_delay(
    *,
    delay_seconds: float,
    turn_cancelled: Callable[[], Awaitable[bool]],
) -> bool:
    if delay_seconds <= 0.0:
        return await turn_cancelled()
    deadline = time.monotonic() + delay_seconds
    while True:
        if await turn_cancelled():
            return True
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0.0:
            return await turn_cancelled()
        await asyncio.sleep(min(remaining_seconds, _RETRY_WAIT_CANCEL_POLL_SECONDS))

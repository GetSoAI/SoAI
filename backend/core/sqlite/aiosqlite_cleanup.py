"""SoAI - Bounded aiosqlite cleanup operations [backend/core/sqlite/aiosqlite_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

__all__ = ("wait_for_aiosqlite_cleanup",)


async def wait_for_aiosqlite_cleanup[CleanupResultT](
    cleanup: Awaitable[CleanupResultT],
) -> CleanupResultT:
    return await uncancel_then_cleanup(asyncio.wait_for(cleanup, timeout=LOCAL_IO_TIMEOUT_SEC))

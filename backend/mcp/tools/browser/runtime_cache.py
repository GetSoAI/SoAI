"""SoAI - Cached PlaywrightBrowserRuntime holder [backend/mcp/tools/browser/runtime_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.browser.playwright_runtime import PlaywrightBrowserRuntime

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "get_cached_playwright_runtime",
    "shutdown_cached_playwright_runtime",
)


@dataclass(slots=True)
class _RuntimeState:
    lock: asyncio.Lock
    runtime: PlaywrightBrowserRuntime | None = None


@functools.lru_cache(maxsize=8)
def _get_runtime_state(_loop: asyncio.AbstractEventLoop) -> _RuntimeState:
    return _RuntimeState(lock=asyncio.Lock())


async def get_cached_playwright_runtime(
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> PlaywrightBrowserRuntime:
    state = _get_runtime_state(asyncio.get_running_loop())
    cached = state.runtime
    if cached is not None:
        return cached
    async with state.lock:
        cached = state.runtime
        if cached is not None:
            return cached
        created = PlaywrightBrowserRuntime(config=config, runtime_flags=runtime_flags)
        state.runtime = created
        return created


async def shutdown_cached_playwright_runtime() -> None:
    state = _get_runtime_state(asyncio.get_running_loop())
    async with state.lock:
        runtime = state.runtime
        state.runtime = None
    if runtime is not None:
        await runtime.shutdown()

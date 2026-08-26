"""SoAI - Async iterator lifecycle helpers [backend/core/concurrency/async_iterators.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.protocols import AsyncClosableIteratorProtocol

__all__ = ("close_async_iterator_if_supported",)


async def close_async_iterator_if_supported[Item](iterator: AsyncIterator[Item]) -> None:
    if isinstance(iterator, AsyncClosableIteratorProtocol):
        await uncancel_then_cleanup(iterator.aclose())

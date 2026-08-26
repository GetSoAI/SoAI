"""SoAI - Lazy bounded pool lifecycle helpers [backend/core/concurrency/bounded_pool_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.concurrency.bounded_blocking import (
    BoundedBlockingPool,
    shutdown_bounded_pool_executor,
)

__all__ = (
    "resolve_lazy_bounded_pool",
    "shutdown_lazy_bounded_pool",
)


def resolve_lazy_bounded_pool(
    current_pool: BoundedBlockingPool | None,
    factory: Callable[[], BoundedBlockingPool],
) -> BoundedBlockingPool:
    if current_pool is not None:
        return current_pool
    return factory()


def shutdown_lazy_bounded_pool(current_pool: BoundedBlockingPool | None) -> None:
    if current_pool is None:
        return
    shutdown_bounded_pool_executor(current_pool)

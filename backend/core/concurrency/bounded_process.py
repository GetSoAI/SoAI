"""SoAI - Bounded process-pool helpers [backend/core/concurrency/bounded_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from concurrent.futures import Executor

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.errors.exceptions import ValidationError

__all__ = ("create_bounded_process_pool",)


def create_bounded_process_pool(
    *,
    executor: Executor,
    label: str,
    max_workers: int,
    max_in_flight: int,
) -> BoundedBlockingPool:
    normalized_label = str(label or "").strip()
    if not normalized_label:
        raise ValidationError("label is required.")
    workers = int(max_workers)
    if workers < 1:
        raise ValidationError("max_workers must be >= 1.")
    in_flight = int(max_in_flight)
    if in_flight < workers:
        raise ValidationError("max_in_flight must be >= max_workers.")
    return BoundedBlockingPool(
        executor=executor,
        semaphore=asyncio.Semaphore(in_flight),
        label=normalized_label,
    )

"""SoAI - Metrics internal protocols [backend/metrics/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from metrics.manager.operations import MetricsQueueFullThrottle

if TYPE_CHECKING:
    import asyncio

    from metrics.manager.types import MetricsWorkerQueueItem

__all__ = ("MetricsOperationEnqueuerProtocol",)


class MetricsOperationEnqueuerProtocol(Protocol):
    _background_queue: asyncio.Queue[MetricsWorkerQueueItem] | None
    _accepting_operations: bool
    _queue_full_throttle: MetricsQueueFullThrottle

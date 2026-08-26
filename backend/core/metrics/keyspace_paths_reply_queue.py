"""SoAI - Reply queue backpressure and delivery metric tuple paths [backend/core/metrics/keyspace_paths_reply_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.metrics.keyspace_base import (
    METRIC_BLOCK_REPLY_QUEUE,
    METRIC_KEY_DELIVERY,
    METRIC_KEY_TERMINAL_FAILED_COUNT,
)

__all__ = ()

REPLY_QUEUE_COUNTER_TERMINAL_DELIVERY_FAILED: tuple[str, ...] = (
    METRIC_BLOCK_REPLY_QUEUE,
    METRIC_KEY_DELIVERY,
    METRIC_KEY_TERMINAL_FAILED_COUNT,
)

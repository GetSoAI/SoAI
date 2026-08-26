"""SoAI - Event bus partition queue selection helpers [backend/core/events/bus_partitioning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import zlib
from typing import TYPE_CHECKING

from core.events.bus_sentinel import EventBusSentinel
from core.events.protocols import (
    ConvIdPartitionKeyProtocol,
    PluginPartitionKeyProtocol,
)
from core.events.types_base import Event

if TYPE_CHECKING:
    from core.events.bus_worker import EventQueueItem

__all__ = ()


def _coerce_partition_value(value: str | float | bool | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if not value:
        return None
    normalized = str(value).strip()
    return normalized or None


def _resolve_partition_key(event: Event) -> str | None:
    if isinstance(event, ConvIdPartitionKeyProtocol):
        user_part = _coerce_partition_value(event.user_id)
        conv_part = _coerce_partition_value(event.conv_id)
        if user_part and conv_part:
            return f"{user_part}:{conv_part}"
    if isinstance(event, PluginPartitionKeyProtocol):
        plugin_part = _coerce_partition_value(event.partition_plugin_name)
        if plugin_part:
            return f"plugin:{plugin_part}"
    return None


def queue_for_event(
    *,
    event: Event,
    queues: list[asyncio.Queue[EventQueueItem | type[EventBusSentinel]]],
    num_workers: int,
    round_robin_index: int,
) -> tuple[asyncio.Queue[EventQueueItem | type[EventBusSentinel]], int]:
    partition_key = _resolve_partition_key(event)
    if partition_key is not None:
        partition_index = zlib.crc32(partition_key.encode("utf-8")) % num_workers
        return queues[partition_index], round_robin_index
    queue = queues[round_robin_index]
    next_round_robin_index = (round_robin_index + 1) % num_workers
    return queue, next_round_robin_index

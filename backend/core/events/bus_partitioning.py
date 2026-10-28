"""SoAI - Event bus partition queue selection helpers [backend/core/events/bus_partitioning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import zlib

from core.events.bus_partitions import EventBusPartitions
from core.events.protocols import (
    ConvIdPartitionKeyProtocol,
    PluginPartitionKeyProtocol,
)
from core.events.types_base import Event

__all__ = ("select_event_partition",)


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


def select_event_partition(*, event: Event, partitions: EventBusPartitions) -> int:
    partition_count = partitions.partition_count
    partition_key = _resolve_partition_key(event)
    if partition_key is not None:
        return zlib.crc32(partition_key.encode("utf-8")) % partition_count
    start = partitions.cursor
    for offset in range(partition_count):
        index = (start + offset) % partition_count
        if partitions.is_live(index):
            partitions.cursor = (index + 1) % partition_count
            return index
    partitions.cursor = (start + 1) % partition_count
    return start

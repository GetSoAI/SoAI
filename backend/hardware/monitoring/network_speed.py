"""SoAI - Network speed snapshot caching [backend/hardware/monitoring/network_speed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms
from hardware.internal_protocols import NetworkSpeedManagerProtocol
from hardware.monitoring.snapshot_coercion import run_async_threadsafe_with_loop

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_network_speed",
    "load_network_speed_from_db",
)

OPERATION = "hardware.load_network_speed_from_db"
BITS_PER_BYTE = 8
BITS_PER_MEGABIT = 1_000_000


def get_network_speed(manager: NetworkSpeedManagerProtocol) -> JSONDict:
    current_stats = psutil.net_io_counters(pernic=True)
    now_monotonic = time.monotonic()
    now_ts_ms = int(epoch_ms())
    speed_stats: JSONDict = {}
    ignored = ("lo", "docker", "veth", "br", "virbr", "kube")
    for iface, data in current_stats.items():
        interface_name = iface.lower()
        if any(interface_name.startswith(prefix) for prefix in ignored):
            continue
        if iface in manager.last_network_stats:
            last_data = manager.last_network_stats[iface]
            timestamp_value = last_data.get("timestamp")
            last_recv = last_data.get("bytes_recv")
            last_sent = last_data.get("bytes_sent")
            if (
                isinstance(timestamp_value, int | float)
                and isinstance(last_recv, int | float)
                and isinstance(last_sent, int | float)
                and (time_delta := now_monotonic - float(timestamp_value)) > 0
            ):
                recv_delta = data.bytes_recv - last_recv
                send_delta = data.bytes_sent - last_sent
                recv_delta = max(recv_delta, 0)
                send_delta = max(send_delta, 0)
                rx_mbps = recv_delta * BITS_PER_BYTE / time_delta / BITS_PER_MEGABIT
                tx_mbps = send_delta * BITS_PER_BYTE / time_delta / BITS_PER_MEGABIT
                speed_stats[iface] = {
                    "download_mbps": round(rx_mbps, 2),
                    "upload_mbps": round(tx_mbps, 2),
                    "observed_at_ms": now_ts_ms,
                }
        manager.last_network_stats[iface] = {
            "bytes_recv": data.bytes_recv,
            "bytes_sent": data.bytes_sent,
            "timestamp": now_monotonic,
        }
    if speed_stats:
        manager.set_network_speed_cache(
            speed_stats,
            cached_at=now_monotonic,
            loaded_from_db=False,
        )
        return speed_stats
    cache_age = now_monotonic - manager.network_speed_cache_timestamp
    need_refresh = (
        not manager.cached_network_speed and (not manager.loaded_network_speed_from_db)
    ) or cache_age > float(manager.network_speed_cache_ttl_seconds)
    if need_refresh:
        snapshot = load_network_speed_from_db(manager)
        if snapshot:
            manager.set_network_speed_cache(
                snapshot,
                cached_at=now_monotonic,
                loaded_from_db=True,
            )
            return snapshot
        manager.set_network_speed_cache(
            manager.cached_network_speed,
            cached_at=manager.network_speed_cache_timestamp,
            loaded_from_db=False,
        )
    return manager.cached_network_speed or {}


def load_network_speed_from_db(manager: NetworkSpeedManagerProtocol) -> JSONDict:
    if not manager.database_hardware:
        return {}
    try:
        result = run_async_threadsafe_with_loop(
            manager.database_hardware.get_latest_network_speed_snapshot(),
            manager.main_loop,
        )
        return result if isinstance(result, dict) else {}
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            manager.logger,
            exception,
            message="Failed to load network speed snapshot",
            operation=OPERATION,
        )
        return {}

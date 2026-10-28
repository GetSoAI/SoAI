"""SoAI - Network speed snapshot caching [backend/hardware/monitoring/network_speed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from copy import deepcopy
from typing import TYPE_CHECKING

import psutil

from core.timing.epoch import epoch_ms
from core.validation.strict_numbers import require_non_negative_int_strict
from hardware.internal_protocols import NetworkSpeedManagerProtocol
from hardware.manager.component_observations import observed_status, unavailable_status
from hardware.monitoring.network_speed_refresh import schedule_network_speed_refresh

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_network_speed",)

OPERATION = "hardware.load_network_speed_from_db"
BITS_PER_BYTE = 8
BITS_PER_MEGABIT = 1_000_000


def get_network_speed(
    manager: NetworkSpeedManagerProtocol,
    *,
    visible_adapter_names: Sequence[str] | None = None,
    observation_status: JSONDict | None = None,
) -> JSONDict:
    now_monotonic = time.monotonic()
    current_stats = psutil.net_io_counters(pernic=True)
    now_ts_ms = require_non_negative_int_strict(
        epoch_ms(), error_message="Network observation timestamp is invalid."
    )
    speed_stats: JSONDict = {}
    ignored = ("lo", "docker", "veth", "br", "virbr", "kube")
    visible_aliases = (
        {name.casefold() for name in visible_adapter_names}
        if visible_adapter_names is not None
        else None
    )
    with manager.state.cache_lock:
        baseline_advanced = False
        for iface, data in current_stats.items():
            if visible_aliases is not None and iface.casefold() not in visible_aliases:
                continue
            if any(iface.lower().startswith(prefix) for prefix in ignored):
                continue
            last_data = manager.last_network_stats.get(iface, {})
            timestamp_value = last_data.get("timestamp")
            last_recv = last_data.get("bytes_recv")
            last_sent = last_data.get("bytes_sent")
            if isinstance(timestamp_value, int | float) and now_monotonic <= timestamp_value:
                continue
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
            baseline_advanced = True
        if baseline_advanced:
            manager.state.network_speed_generation += 1
        if speed_stats:
            manager.set_network_speed_cache(
                speed_stats, cached_at=now_monotonic, loaded_from_db=False
            )
            if observation_status is not None:
                observation_status.update(observed_status(now_ts_ms))
                observation_status["sampled_current"] = True
            return speed_stats
        previous_cache_time = manager.network_speed_cache_timestamp
        cache_age = now_monotonic - previous_cache_time
        need_refresh = (
            not manager.cached_network_speed and not manager.loaded_network_speed_from_db
        ) or cache_age > float(manager.network_speed_cache_ttl_seconds)
        if need_refresh:
            schedule_network_speed_refresh(manager, now_monotonic)
        cached = deepcopy(manager.cached_network_speed or {})
    if visible_aliases is not None:
        cached = {
            name: value for name, value in cached.items() if name.casefold() in visible_aliases
        }
    if observation_status is not None:
        times = [
            int(timestamp)
            for value in cached.values()
            if isinstance(value, dict)
            and isinstance(timestamp := value.get("observed_at_ms"), int | float)
            and not isinstance(timestamp, bool)
            and math.isfinite(timestamp)
            and timestamp >= 0
            and int(timestamp) == timestamp
        ]
        observation_status.update(
            observed_status(now_ts_ms, status="stale")
            if times
            else unavailable_status(now_ts_ms, error_code="monitoring_sample_unavailable")
        )
        observation_status["observed_at_ms"] = min(times) if times else None
        observation_status["sampled_current"] = False
        if times:
            observation_status["age_ms"] = max(0, now_ts_ms - min(times))
    return cached

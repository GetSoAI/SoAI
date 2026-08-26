"""SoAI - Hardware manager runtime state container [backend/hardware/manager/manager_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from concurrent import futures
from dataclasses import dataclass, field

from core.types.json import JSONDict, JSONValue
from hardware.manager.speed_cache import DiskSpeedCacheState, NetworkSpeedCacheState

__all__ = ("HardwareManagerState",)


@dataclass(slots=True)
class HardwareManagerState:
    min_specs_task: asyncio.Task[None] | None = None
    monitoring_thread: threading.Thread | None = None
    monitoring_stop_event: threading.Event = field(default_factory=threading.Event)
    cache_lock: threading.Lock = field(default_factory=threading.Lock)
    last_full_info: JSONDict = field(default_factory=dict[str, JSONValue])
    last_update_time_monotonic: float = 0.0
    main_loop: asyncio.AbstractEventLoop | None = None
    os_info: JSONDict = field(default_factory=dict[str, JSONValue])
    last_network_stats: dict[str, JSONDict] = field(default_factory=dict[str, JSONDict])
    disk_speed_cache: DiskSpeedCacheState = field(default_factory=DiskSpeedCacheState)
    disk_speed_refresh_future: futures.Future[JSONDict | None] | None = None
    network_speed_cache: NetworkSpeedCacheState = field(default_factory=NetworkSpeedCacheState)

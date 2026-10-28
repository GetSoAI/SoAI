"""SoAI - Hardware manager runtime state container [backend/hardware/manager/manager_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from concurrent import futures
from dataclasses import dataclass, field

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.singleflight import AsyncSingleflight
from core.logging.rate_limited_logger import RateLimitedLogger
from core.types.json import JSONDict, JSONValue
from hardware.manager.component_observations import ComponentObservation
from hardware.manager.speed_cache import DiskSpeedCacheState, NetworkSpeedCacheState
from hardware.manager.windows_static_inventory import WindowsStaticInventoryState

__all__ = ("HardwareManagerState",)


@dataclass(slots=True)
class HardwareManagerState:
    system_capability_pool: BoundedBlockingPool | None = None
    system_capability_generation: int = 0
    system_capability_stopping: bool = False
    system_capability_acquisitions: int = 0
    system_capability_idle: asyncio.Event = field(default_factory=asyncio.Event)
    system_capability_singleflight: AsyncSingleflight[tuple[int, int], JSONDict] = field(
        default_factory=AsyncSingleflight[tuple[int, int], JSONDict]
    )
    lifecycle_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    min_specs_task: asyncio.Task[None] | None = None
    windows_static_inventory: WindowsStaticInventoryState = field(
        default_factory=WindowsStaticInventoryState
    )
    monitoring_thread: threading.Thread | None = None
    monitoring_stop_event: threading.Event = field(default_factory=threading.Event)
    cache_lock: threading.Lock = field(default_factory=threading.Lock)
    last_full_info: JSONDict = field(default_factory=dict[str, JSONValue])
    last_update_time_monotonic: float = 0.0
    issued_network_query_sequence: int = 0
    committed_network_query_sequence: int = 0
    component_observations: dict[str, ComponentObservation] = field(
        default_factory=dict[str, ComponentObservation]
    )
    issued_component_sequences: dict[str, int] = field(default_factory=dict[str, int])
    component_diagnostic_limits: dict[str, RateLimitedLogger] = field(
        default_factory=dict[str, RateLimitedLogger]
    )
    main_loop: asyncio.AbstractEventLoop | None = None
    os_info: JSONDict = field(default_factory=dict[str, JSONValue])
    last_network_stats: dict[str, JSONDict] = field(default_factory=dict[str, JSONDict])
    disk_speed_cache: DiskSpeedCacheState = field(default_factory=DiskSpeedCacheState)
    disk_speed_refresh_task: asyncio.Task[JSONDict | None] | None = None
    disk_speed_refresh_future: futures.Future[JSONDict | None] | None = None
    network_speed_cache: NetworkSpeedCacheState = field(default_factory=NetworkSpeedCacheState)
    network_speed_refresh_task: asyncio.Task[None] | None = None
    network_speed_refresh_future: futures.Future[None] | None = None
    network_speed_refresh_completed_monotonic: float | None = None
    network_speed_refresh_failed: bool = False
    network_speed_generation: int = 0

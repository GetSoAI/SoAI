"""SoAI - Off-tick Windows static inventory observations [backend/hardware/manager/windows_static_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.concurrency.singleflight import SyncSingleflight
from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from hardware.info_motherboard import read_windows_motherboard
from hardware.manager.component_observations import (
    OPTIONAL_PROBE_EXCEPTIONS,
    ComponentObservation,
    accept_component_observations,
    observed_status,
    unavailable_status,
)
from hardware.windows_cpu_info import get_windows_cpu_info
from hardware.windows_network_adapters import query_windows_visible_adapter_names

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol

__all__ = (
    "WINDOWS_STATIC_REFRESH_SECONDS",
    "STATIC_COMPONENTS",
    "WindowsStaticInventoryState",
    "read_windows_static_inventory",
    "refresh_windows_static_inventory",
    "run_windows_static_inventory_refresh",
)

WINDOWS_STATIC_REFRESH_SECONDS = 300.0
STATIC_COMPONENTS = ("cpus", "network", "motherboard")


@dataclass(slots=True)
class WindowsStaticInventoryState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    stopped: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task[None] | None = None
    sequence: int = 0
    snapshot: JSONDict = field(default_factory=dict[str, JSONValue])
    observations: dict[str, ComponentObservation] = field(
        default_factory=dict[str, ComponentObservation]
    )
    singleflight: SyncSingleflight[str, JSONDict] = field(
        default_factory=SyncSingleflight[str, JSONDict]
    )
    refresh_eligibility: TTLCache[str, bool] = field(
        default_factory=lambda: TTLCache(
            TTLCacheDependencies(ttl_seconds=WINDOWS_STATIC_REFRESH_SECONDS, max_size=1)
        )
    )


def read_windows_static_inventory(state: WindowsStaticInventoryState) -> JSONDict:
    with state.lock:
        snapshot = deepcopy(state.snapshot)
    if "component_status" not in snapshot:
        snapshot["component_status"] = {}
    metadata = snapshot["component_status"]
    if isinstance(metadata, dict):
        for component in STATIC_COMPONENTS:
            initial_status = unavailable_status(
                epoch_ms(), error_code="monitoring_inventory_unavailable"
            )
            if component not in metadata:
                metadata[component] = initial_status
    return snapshot


def _collect_windows_static_inventory(
    state: WindowsStaticInventoryState, executor: CommandExecutorProtocol
) -> JSONDict | None:
    if state.stopped.is_set():
        return None
    snapshot: JSONDict = {}
    metadata: JSONDict = {}
    try:
        cpus = get_windows_cpu_info(executor)
        if cpus:
            snapshot["cpus"] = cpus
            metadata["cpus"] = observed_status(epoch_ms())
        else:
            metadata["cpus"] = unavailable_status(
                epoch_ms(), error_code="monitoring_inventory_unavailable"
            )
    except OPTIONAL_PROBE_EXCEPTIONS:
        metadata["cpus"] = unavailable_status(
            epoch_ms(), error_code="monitoring_inventory_unavailable"
        )
    if state.stopped.is_set():
        return None
    try:
        names = query_windows_visible_adapter_names(executor)
        if names is not None:
            snapshot["network"] = {"visible_adapter_names": list(names)}
            metadata["network"] = observed_status(epoch_ms())
        else:
            metadata["network"] = unavailable_status(
                epoch_ms(), error_code="monitoring_inventory_unavailable"
            )
    except OPTIONAL_PROBE_EXCEPTIONS:
        metadata["network"] = unavailable_status(
            epoch_ms(), error_code="monitoring_inventory_unavailable"
        )
    if state.stopped.is_set():
        return None
    try:
        motherboard = read_windows_motherboard(executor)
        if motherboard.state == "observed":
            snapshot["motherboard"] = motherboard.info
            metadata["motherboard"] = observed_status(epoch_ms())
        else:
            metadata["motherboard"] = unavailable_status(
                epoch_ms(), error_code=f"motherboard_{motherboard.state}"
            )
    except OPTIONAL_PROBE_EXCEPTIONS:
        metadata["motherboard"] = unavailable_status(
            epoch_ms(), error_code="monitoring_inventory_unavailable"
        )
    snapshot["component_status"] = metadata
    return snapshot


def refresh_windows_static_inventory(
    state: WindowsStaticInventoryState,
    executor: CommandExecutorProtocol,
) -> JSONDict:
    def acquire_if_due() -> JSONDict:
        if state.stopped.is_set() or state.refresh_eligibility.get("inventory") is not None:
            return read_windows_static_inventory(state)
        candidate = _collect_windows_static_inventory(state, executor)
        if candidate is None:
            return read_windows_static_inventory(state)
        with state.lock:
            if not state.stopped.is_set():
                state.sequence += 1
                accept_component_observations(
                    cached=state.snapshot,
                    observations=state.observations,
                    sequences={component: state.sequence for component in STATIC_COMPONENTS},
                    snapshot=candidate,
                    checked_monotonic=time.monotonic(),
                    checked_at_ms=epoch_ms(),
                )
                state.refresh_eligibility.put("inventory", True)
        return read_windows_static_inventory(state)

    return state.singleflight.execute_or_wait("inventory", acquire_if_due)


async def run_windows_static_inventory_refresh(
    state: WindowsStaticInventoryState,
    executor: CommandExecutorProtocol,
) -> None:
    while not state.stopped.is_set():
        await run_joined_thread_call(
            refresh_windows_static_inventory,
            state,
            executor,
            task_name="hardware-windows-static-inventory-worker",
            retain_resources_until_complete=True,
            on_cancel=state.stopped.set,
        )
        await asyncio.sleep(WINDOWS_STATIC_REFRESH_SECONDS)

"""SoAI - Active inference tracking for orchestrator executor [backend/orchestrator/execution/active_inferences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from core.di.validation import require_dependencies
from core.events.types_base import Event

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "ActiveInferenceInfo",
    "ActiveInferenceInfoBase",
    "ActiveInferenceRegistry",
    "ActiveInferenceRegistryDependencies",
)


class ActiveInferenceInfoBase(TypedDict):
    tracking_id: str
    task_id: str
    cancellation_id: str
    context: JSONDict
    plugin_name: str
    model_uid: str
    start_time: float
    last_progress_time: float
    stream_activity_seen: bool
    is_streaming: bool
    is_persistent: bool
    reply_channel: asyncio.Queue[Event] | None
    task: asyncio.Task[bool]


class ActiveInferenceInfo(ActiveInferenceInfoBase, total=False):
    dispatch_time: float
    request_timeout_sec: float


PROGRESS_UPDATE_THROTTLE_SECONDS: float = 0.1


@dataclass(frozen=True, slots=True)
class ActiveInferenceRegistryDependencies:
    def __post_init__(self) -> None:
        require_dependencies(owner="ActiveInferenceRegistryDependencies")


class ActiveInferenceRegistry:
    def __init__(self, deps: ActiveInferenceRegistryDependencies) -> None:
        self._deps = deps
        self.lock = asyncio.Lock()
        self._active: dict[str, ActiveInferenceInfo] = {}
        self._next_progress_update_time: dict[str, float] = {}

    async def register(self, tracking_id: str, info: ActiveInferenceInfo) -> None:
        async with self.lock:
            self._active[tracking_id] = info
            self._next_progress_update_time[tracking_id] = 0.0

    async def pop(self, tracking_id: str) -> ActiveInferenceInfo | None:
        async with self.lock:
            self._next_progress_update_time.pop(tracking_id, None)
            return self._active.pop(tracking_id, None)

    async def get(self, tracking_id: str) -> ActiveInferenceInfo | None:
        async with self.lock:
            return self._active.get(tracking_id)

    async def update_progress(self, tracking_id: str) -> None:
        current_time = time.monotonic()
        next_allowed_time = self._next_progress_update_time.get(tracking_id)
        if next_allowed_time is not None and current_time < next_allowed_time:
            return
        async with self.lock:
            info = self._active.get(tracking_id)
            if info is None:
                self._next_progress_update_time.pop(tracking_id, None)
                return
            now = time.monotonic()
            next_allowed_time = self._next_progress_update_time.get(tracking_id, 0.0)
            if now < next_allowed_time:
                return
            info["last_progress_time"] = now
            info["stream_activity_seen"] = True
            self._next_progress_update_time[tracking_id] = now + PROGRESS_UPDATE_THROTTLE_SECONDS

    async def set_dispatch_time(self, tracking_id: str, dispatch_time: float) -> None:
        async with self.lock:
            info = self._active.get(tracking_id)
            if info is not None:
                info["dispatch_time"] = dispatch_time

    async def set_request_timeout(self, tracking_id: str, timeout: float) -> None:
        async with self.lock:
            info = self._active.get(tracking_id)
            if info is not None:
                info["request_timeout_sec"] = timeout

    async def get_dispatch_time(self, tracking_id: str) -> float | None:
        async with self.lock:
            info = self._active.get(tracking_id)
            if info is not None:
                dispatch_time = info.get("dispatch_time")
                return dispatch_time if isinstance(dispatch_time, int | float) else None
            return None

    async def list_for_plugin(self, plugin_name: str) -> list[ActiveInferenceInfo]:
        async with self.lock:
            return [info for info in self._active.values() if info["plugin_name"] == plugin_name]

    async def count_for_plugin(self, plugin_name: str) -> int:
        async with self.lock:
            return sum(1 for info in self._active.values() if info["plugin_name"] == plugin_name)

    async def has_tracking_id(self, tracking_id: str) -> bool:
        async with self.lock:
            return tracking_id in self._active

    async def tasks(self) -> list[asyncio.Task[bool]]:
        async with self.lock:
            return [info["task"] for info in self._active.values()]

    async def snapshot(self) -> list[JSONDict]:
        async with self.lock:
            snapshots: list[JSONDict] = []
            for info in self._active.values():
                snapshot: JSONDict = {
                    "tracking_id": info["tracking_id"],
                    "task_id": info["task_id"],
                    "cancellation_id": info["cancellation_id"],
                    "context": info["context"],
                    "plugin_name": info["plugin_name"],
                    "model_uid": info["model_uid"],
                    "start_time": info["start_time"],
                    "last_progress_time": info["last_progress_time"],
                    "stream_activity_seen": info["stream_activity_seen"],
                    "is_streaming": info["is_streaming"],
                    "is_persistent": info["is_persistent"],
                }
                dispatch_time = info.get("dispatch_time")
                if dispatch_time is not None:
                    snapshot["dispatch_time"] = dispatch_time
                request_timeout = info.get("request_timeout_sec")
                if request_timeout is not None:
                    snapshot["request_timeout_sec"] = request_timeout
                snapshots.append(snapshot)
            return snapshots

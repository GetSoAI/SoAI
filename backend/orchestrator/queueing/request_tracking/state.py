"""SoAI - Request tracking state [backend/orchestrator/queueing/request_tracking/state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass

from core.tasks.task import Task

__all__ = (
    "QueueRequestTrackingState",
    "create_tracking_state",
)


@dataclass(slots=True)
class QueueRequestTrackingState:
    active_tasks: dict[str, Task]
    tracking_ids_by_task_id: defaultdict[str, set[str]]
    tasks_by_id: dict[str, Task]
    task_ids_by_cancellation_id: defaultdict[str, set[str]]
    pending_by_routing_key: defaultdict[str, deque[str]]
    pending_total_count: int
    pending_keys: defaultdict[str, set[str]]
    pending_entries: dict[str, Task]
    pending_universal_ids_by_plugin: defaultdict[str, set[str]]
    last_deferral_reason: dict[str, str]
    tasks_lock: asyncio.Lock


def create_tracking_state() -> QueueRequestTrackingState:
    return QueueRequestTrackingState(
        active_tasks={},
        tracking_ids_by_task_id=defaultdict(set),
        tasks_by_id={},
        task_ids_by_cancellation_id=defaultdict(set),
        pending_by_routing_key=defaultdict(deque),
        pending_total_count=0,
        pending_keys=defaultdict(set),
        pending_entries={},
        pending_universal_ids_by_plugin=defaultdict(set),
        last_deferral_reason={},
        tasks_lock=asyncio.Lock(),
    )

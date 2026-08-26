"""SoAI - Plugin queue capacity exceptions [backend/orchestrator/capacity/plugin_queue/errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError

__all__ = (
    "OPERATION_ORCHESTRATOR_CAPACITY_ENQUEUE_PLUGIN_TASK",
    "PluginQueueFullError",
)

OPERATION_ORCHESTRATOR_CAPACITY_ENQUEUE_PLUGIN_TASK = "orchestrator.capacity.enqueue_plugin_task"


class PluginQueueFullError(StateError):
    __slots__ = ()

"""SoAI - Queue-cycle domain exceptions [backend/orchestrator/queueing/cycle_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.orchestrator.protocols_queue import QueueCycleType

__all__ = (
    "OPERATION_ORCHESTRATOR_QUEUE_CYCLES_OPEN_PLUGIN",
    "OPERATION_ORCHESTRATOR_QUEUE_CYCLES_OPEN_PRIORITY",
    "PluginQueueCycleAlreadyOpenError",
    "PriorityQueueCycleAlreadyOpenError",
    "QueueCycleAlreadyOpenError",
    "queue_cycle_already_open_error_type",
    "queue_cycle_open_operation",
)

OPERATION_ORCHESTRATOR_QUEUE_CYCLES_OPEN_PLUGIN = "orchestrator.queue_cycles.open_plugin"
OPERATION_ORCHESTRATOR_QUEUE_CYCLES_OPEN_PRIORITY = "orchestrator.queue_cycles.open_priority"


def queue_cycle_open_operation(cycle_type: QueueCycleType) -> str:
    if cycle_type is QueueCycleType.PRIORITY:
        return OPERATION_ORCHESTRATOR_QUEUE_CYCLES_OPEN_PRIORITY
    return OPERATION_ORCHESTRATOR_QUEUE_CYCLES_OPEN_PLUGIN


def queue_cycle_already_open_error_type(
    cycle_type: QueueCycleType,
) -> type[QueueCycleAlreadyOpenError]:
    if cycle_type is QueueCycleType.PRIORITY:
        return PriorityQueueCycleAlreadyOpenError
    return PluginQueueCycleAlreadyOpenError


class QueueCycleAlreadyOpenError(StateError):
    __slots__ = ()


class PluginQueueCycleAlreadyOpenError(QueueCycleAlreadyOpenError):
    __slots__ = ()


class PriorityQueueCycleAlreadyOpenError(QueueCycleAlreadyOpenError):
    __slots__ = ()

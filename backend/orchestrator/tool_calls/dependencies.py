"""SoAI - Orchestrator tool-call processing dependencies [backend/orchestrator/tool_calls/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tool_calls.protocols import (
    DatabaseToolCallsProtocol,
    ToolCallExecutorProtocol,
)

__all__ = ("ToolCallProcessorDependencies",)


@dataclass(frozen=True, slots=True)
class ToolCallProcessorDependencies:
    database_tool_calls: DatabaseToolCallsProtocol
    tool_executor: ToolCallExecutorProtocol
    event_bus: EventBusProtocol | None
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ToolCallProcessorDependencies",
            cancellation_binder=self.cancellation_binder,
            database_tool_calls=self.database_tool_calls,
            finalizer_tracker=self.finalizer_tracker,
            tool_executor=self.tool_executor,
        )

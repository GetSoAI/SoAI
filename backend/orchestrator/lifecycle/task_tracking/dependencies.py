"""SoAI - Task tracking dependency types [backend/orchestrator/lifecycle/task_tracking/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.orchestrator.protocols_lifecycle import OrchestratorLifecyclePublisherProtocol
from orchestrator.internal_protocols import OrchestratorCapacityProtocol
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("TaskTrackingDependencies",)


@dataclass(frozen=True, slots=True)
class TaskTrackingDependencies:
    orchestrator: OrchestratorDependencies
    capacity: OrchestratorCapacityProtocol
    state: LifecycleStateAccessorProtocol
    shutdown_event: asyncio.Event
    lifecycle_publisher: OrchestratorLifecyclePublisherProtocol
    tool_name_extractor: Callable[[list[JSONValue]], list[str]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TaskTrackingDependencies",
            capacity=self.capacity,
            lifecycle_publisher=self.lifecycle_publisher,
            orchestrator=self.orchestrator,
            shutdown_event=self.shutdown_event,
            state=self.state,
            tool_name_extractor=self.tool_name_extractor,
        )

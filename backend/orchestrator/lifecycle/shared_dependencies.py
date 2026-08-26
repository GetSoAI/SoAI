"""SoAI - Shared lifecycle dependency bases [backend/orchestrator/lifecycle/shared_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.protocols_lifecycle import OrchestratorLifecyclePublisherProtocol
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)
from orchestrator.types import OrchestratorDependencies

__all__ = ("LifecycleSharedDependencies",)


@dataclass(frozen=True, slots=True)
class LifecycleSharedDependencies:
    orchestrator: OrchestratorDependencies
    shutdown_event: asyncio.Event
    state: LifecycleStateAccessorProtocol
    lifecycle_publisher: OrchestratorLifecyclePublisherProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="LifecycleSharedDependencies",
            lifecycle_publisher=self.lifecycle_publisher,
            orchestrator=self.orchestrator,
            shutdown_event=self.shutdown_event,
            state=self.state,
        )

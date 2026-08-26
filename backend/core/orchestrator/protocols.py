"""SoAI - Orchestrator aggregate protocol contracts [backend/core/orchestrator/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.orchestrator.protocols_lifecycle import (
    OrchestratorControlProtocol,
    OrchestratorLifecycleProtocol,
)
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol

__all__ = ("OrchestratorProtocolContracts",)


class OrchestratorProtocolContracts(Protocol):
    @property
    def control(self) -> OrchestratorControlProtocol: ...

    @property
    def lifecycle(self) -> OrchestratorLifecycleProtocol: ...

    @property
    def queue(self) -> OrchestratorQueueProtocol: ...

    @property
    def scheduler(self) -> OrchestratorSchedulerProtocol: ...

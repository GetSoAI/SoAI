"""SoAI - Orchestrator services internal protocols [backend/features/api/runtime/container/protocol_groups/service_protocols/orchestrator/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorControlProtocol,
        OrchestratorLifecycleProtocol,
    )
    from core.tool_calls.protocols import ToolCallProcessingProtocol

__all__ = ("OrchestratorServicesProtocol",)


class OrchestratorServicesProtocol(Protocol):
    @property
    def control(self) -> OrchestratorControlProtocol: ...

    @property
    def lifecycle(self) -> OrchestratorLifecycleProtocol: ...

    @property
    def tool_call_processor(self) -> ToolCallProcessingProtocol: ...

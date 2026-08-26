"""SoAI - API runtime service composition result [backend/features/api/runtime/container/api_runtime_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.agent.protocols import (
    AgentChronologySequencerProtocol,
    AgentStateServiceProtocol,
)
from core.di.validation import require_dependencies
from core.events.types_base import Event
from core.features.protocols import CommandDispatcherProtocol

__all__ = ("ApiRuntimeServices",)


@dataclass(frozen=True, slots=True)
class ApiRuntimeServices:
    command_dispatcher: CommandDispatcherProtocol[Event]
    agent_chronology_sequencer: AgentChronologySequencerProtocol
    agent_state_service: AgentStateServiceProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ApiRuntimeServices",
            command_dispatcher=self.command_dispatcher,
            agent_chronology_sequencer=self.agent_chronology_sequencer,
            agent_state_service=self.agent_state_service,
        )

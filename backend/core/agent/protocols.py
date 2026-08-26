"""SoAI - Cross-subsystem agent protocol contracts [backend/core/agent/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from core.execution.protocols import AgentTurnIdentityFields

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.execution.protocols import SubagentSnapshot
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "AgentChronologySequencerProtocol",
    "AgentStateServiceProtocol",
    "AgentSubagentServiceProtocol",
    "AgentTurnCoreFields",
    "PersistedAgentStateProtocol",
    "SubagentAcceptedExecution",
    "SubagentCancelResult",
    "SubagentSpawnRequest",
)


@dataclass(frozen=True, slots=True)
class SubagentSpawnRequest:
    task: str
    context: str | None
    mode: str | None
    display_name: str | None
    model: str | None
    workspace_path: str | None
    max_iterations: int | None
    tools: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class SubagentAcceptedExecution:
    subagent_id: str
    owner_task_id: str
    status: str
    mode: str
    conv_id: str
    requested_model: str | None


@dataclass(frozen=True, slots=True)
class SubagentCancelResult:
    cancelled: bool


@dataclass(frozen=True, slots=True)
class AgentTurnCoreFields(AgentTurnIdentityFields):
    requested_model: str | None
    owner_task_id: str | None
    execution_token: str
    server_boot_id: str


class AgentSubagentServiceProtocol(Protocol):
    async def spawn_subagent(self, request: SubagentSpawnRequest) -> SubagentAcceptedExecution: ...

    async def get_subagent(self, *, subagent_id: str) -> SubagentSnapshot | None: ...

    async def wait_for_subagent(
        self,
        *,
        subagent_id: str,
        timeout_ms: int | None,
    ) -> SubagentSnapshot | None: ...

    async def cancel_subagent(self, *, subagent_id: str) -> SubagentCancelResult: ...


class AgentChronologySequencerProtocol(Protocol):
    async def next_sequence(self, *, conv_id: str, user_id: int) -> int: ...

    def peek_last_issued(self, *, conv_id: str, user_id: int) -> int: ...


class PersistedAgentStateProtocol(Protocol):
    @property
    def payload(self) -> JSONDict: ...

    @property
    def event(self) -> Event: ...


class AgentStateServiceProtocol(Protocol):
    async def get_todo_payload(self, *, conv_id: str, user_id: int) -> JSONDict: ...

    async def read_plan_payload(self, *, conv_id: str, user_id: int) -> JSONDict: ...

    async def persist_todo_state(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        iteration_index: int,
        todo_value: JSONValue,
        explanation_value: JSONValue,
        require_no_running_root_turn: bool,
    ) -> PersistedAgentStateProtocol: ...

    async def persist_plan_state(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        iteration_index: int,
        title_value: JSONValue,
        markdown_value: JSONValue,
        require_no_running_root_turn: bool,
    ) -> PersistedAgentStateProtocol: ...

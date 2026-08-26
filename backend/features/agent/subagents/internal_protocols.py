"""SoAI - Subagent internal protocol definitions [backend/features/agent/subagents/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict

__all__ = (
    "SubagentBackgroundExecutorProtocol",
    "SubagentEventPayloadProtocol",
)


class SubagentBackgroundExecutorProtocol(Protocol):
    async def execute(
        self,
        *,
        subagent_context: RequestContext,
        subagent_tool_context: MCPToolContext,
        requested_model: str,
        settings: AgentSettings,
        execution_request: JSONDict,
        coordinator_task_id: str,
        task_text: str,
        task_context: str | None,
    ) -> None: ...


class SubagentEventPayloadProtocol(Protocol):
    @property
    def trace_id(self) -> str | None: ...

    @property
    def event_id(self) -> str: ...

    @property
    def timestamp(self) -> float: ...

    @property
    def user_id(self) -> int: ...

    @property
    def conv_id(self) -> str: ...

    @property
    def parent_turn_id(self) -> str: ...

    @property
    def parent_tool_call_id(self) -> str: ...

    @property
    def parent_iteration_index(self) -> int: ...

    @property
    def subagent_id(self) -> str: ...

    @property
    def execution_type(self) -> str: ...

    @property
    def display_name(self) -> str | None: ...

    @property
    def mode(self) -> str: ...

    @property
    def owner_task_id(self) -> str | None: ...

    @property
    def status(self) -> str: ...

    @property
    def status_message(self) -> str | None: ...

    @property
    def started_at_ms(self) -> int: ...

    @property
    def updated_at_ms(self) -> int: ...

    @property
    def finished_at_ms(self) -> int | None: ...

    @property
    def requested_model(self) -> str | None: ...

    @property
    def result_text(self) -> str | None: ...

    @property
    def result_text_delta(self) -> str | None: ...

    @property
    def error_message(self) -> str | None: ...

    @property
    def error_type(self) -> str | None: ...

    @property
    def token_usage(self) -> JSONDict | None: ...

    @property
    def item_id(self) -> str | None: ...

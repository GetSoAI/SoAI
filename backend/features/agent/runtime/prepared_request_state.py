"""SoAI - Prepared agent request state for shared execution flows [backend/features/agent/runtime/prepared_request_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.orchestrator.types import MCPToolContext
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )

__all__ = ("PreparedExecutionRequest",)


@dataclass(frozen=True, slots=True)
class PreparedExecutionRequest:
    conv_id: str
    user_id: int
    requested_model: str | None
    agent_settings: AgentSettings
    todo_state: JSONDict | None
    prepared_messages_before_compaction: list[JSONDict]
    prepared_messages_after_compaction: list[JSONDict]
    source_messages: list[JSONDict]
    boundary_source_messages: list[JSONDict]
    source_policy: str = ""
    request_json: JSONDict = field(default_factory=dict[str, JSONValue])
    subagent_summaries: list[JSONDict] = field(default_factory=list[JSONDict])
    tool_context: MCPToolContext | None = None
    final_payload: JSONDict = field(default_factory=dict[str, JSONValue])
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None = None

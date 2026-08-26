"""SoAI - Agent state manual edit policy [backend/features/agent/runtime/agent_state_manual_edit_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.agent.state_errors import (
    AgentStateManualEditConflictError,
    AgentStateManualEditUnavailableError,
)
from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
from core.tasks.protocols import TokenCollectionProtocol
from core.tasks.protocols_query import TaskRegistryQueryView
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from features.agent.runtime.turn_state_reconciliation import reconcile_running_turns

__all__ = ("ensure_manual_edit_allowed",)


async def ensure_manual_edit_allowed(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol | None,
    database_tool_calls: DatabaseToolCallsProtocol | None,
    task_registry_queries: TaskRegistryQueryView | None,
    token_collection: TokenCollectionProtocol | None,
    conv_id: str,
    user_id: int,
) -> None:
    if (
        database_agent_turns is None
        or database_tool_calls is None
        or task_registry_queries is None
        or token_collection is None
    ):
        raise AgentStateManualEditUnavailableError()
    live_turns = await reconcile_running_turns(
        database_agent_turns=database_agent_turns,
        database_tool_calls=database_tool_calls,
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        conv_id=conv_id,
        user_id=user_id,
    )
    if live_turns:
        raise AgentStateManualEditConflictError()

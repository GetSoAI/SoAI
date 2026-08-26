"""SoAI - Subagent snapshot query and serialization helpers [backend/features/agent/subagents/summaries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import SUBAGENT_STATUS_RUNNING
from core.agent.subagent_serialization import serialize_subagent_snapshots
from core.execution.protocols import SubagentSnapshot
from features.agent.subagents.reads import list_subagent_snapshots
from features.agent.subagents.result_excerpt_trimming import (
    trim_prompt_summary_result_excerpt,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.tasks.protocols import TokenCollectionProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.types.json import JSONDict

__all__ = (
    "list_running_subagent_snapshots",
    "list_serialized_subagent_snapshots_for_prompt",
)


async def list_serialized_subagent_snapshots_for_prompt(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    parent_turn_id: str | None = None,
) -> list[JSONDict]:
    snapshots = await list_subagent_snapshots(
        database_agent_turns=database_agent_turns,
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        conv_id=conv_id,
        user_id=user_id,
        parent_turn_id=parent_turn_id,
    )
    serialized = serialize_subagent_snapshots(snapshots)
    for entry in serialized:
        result_text = entry.get("result_text")
        if isinstance(result_text, str) and result_text.strip():
            entry["result_text"] = trim_prompt_summary_result_excerpt(result_text)
    return serialized


async def list_running_subagent_snapshots(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    parent_turn_id: str | None = None,
) -> list[SubagentSnapshot]:
    snapshots = await list_subagent_snapshots(
        database_agent_turns=database_agent_turns,
        task_registry_queries=task_registry_queries,
        token_collection=token_collection,
        conv_id=conv_id,
        user_id=user_id,
        parent_turn_id=parent_turn_id,
    )
    return [snapshot for snapshot in snapshots if snapshot.status == SUBAGENT_STATUS_RUNNING]

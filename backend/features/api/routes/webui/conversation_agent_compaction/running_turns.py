"""SoAI - Manual compaction running-turn guard [backend/features/api/routes/webui/conversation_agent_compaction/running_turns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.agent.runtime.turn_state_reconciliation import reconcile_running_turns
from features.api.runtime.errors import raise_conflict

if TYPE_CHECKING:
    from starlette.requests import Request

    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("load_live_agent_turns", "require_no_running_agent_turns")


async def require_no_running_agent_turns(
    request: Request,
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
) -> None:
    live_turns = await load_live_agent_turns(
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    if live_turns:
        raise_conflict(request, "Compaction unavailable while agent is running.")


async def load_live_agent_turns(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
) -> list[JSONDict]:
    return await reconcile_running_turns(
        database_agent_turns=api_context.dependencies.database_agent_turns,
        database_tool_calls=api_context.dependencies.database_tool_calls,
        task_registry_queries=api_context.dependencies.task_registry_queries,
        token_collection=api_context.dependencies.token_collection,
        conv_id=conv_id,
        user_id=user_id,
    )

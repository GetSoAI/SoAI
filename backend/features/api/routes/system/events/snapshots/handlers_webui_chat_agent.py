"""SoAI - Snapshot handlers for WebUI chat agent state [backend/features/api/routes/system/events/snapshots/handlers_webui_chat_agent.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.agent.state_payloads import read_agent_plan_payload, read_agent_todo_payload
from core.agent.status_values import (
    SUBAGENT_STATUS_ABANDONED,
    SUBAGENT_STATUS_CANCELLED,
    SUBAGENT_STATUS_COMPLETED,
    SUBAGENT_STATUS_ERROR,
    SUBAGENT_STATUS_MAX_ITERATIONS,
    SUBAGENT_STATUS_RUNNING,
)
from core.agent.turn_snapshot import require_agent_turn_snapshot
from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from features.agent.subagents.reads import list_subagent_snapshots
from features.api.routes.webui.conversation_agent_compaction.running_turns import (
    load_live_agent_turns,
)
from features.api.runtime.agent_state_payloads import build_agent_checkpoint_payload
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.context import ApiContext

__all__ = (
    "snapshot_webui_chat_agent_checkpoint",
    "snapshot_webui_chat_agent_plan",
    "snapshot_webui_chat_agent_todo",
)


def _require_snapshot_conversation_id(
    data: JSONDict,
    connection: WebsocketConnection,
) -> tuple[str, int]:
    conv_id_value = data.get("conv_id")
    conv_id = conv_id_value.strip() if isinstance(conv_id_value, str) else ""
    if not conv_id:
        raise ValidationError("Agent snapshot requires conv_id.")
    user_id_value = connection.user.get("id")
    if not is_strict_int(user_id_value):
        raise ValidationError("Agent snapshot user id is invalid.")
    user_id = int(user_id_value)
    return conv_id, user_id


async def _require_existing_conversation(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
) -> str:
    conversation = await api_context.dependencies.database_conversations.get_conversation(
        conv_id,
        user_id,
    )
    if conversation is None:
        raise ValidationError("Conversation not found.")
    conversation_id = conversation.get("id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise ValidationError("Conversation record is invalid.")
    return conversation_id.strip()


async def _build_checkpoint_payload(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
) -> JSONDict | None:
    live_turns = await load_live_agent_turns(
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    turn_record: JSONDict | None
    if live_turns:
        turn_record = live_turns[0]
    else:
        turn_record = await api_context.dependencies.database_agent_turns.get_latest_finalized_turn(
            conv_id=conv_id,
            user_id=user_id,
        )
    if turn_record is None:
        return None
    turn_snapshot = require_agent_turn_snapshot(turn_record)
    subagent_snapshots = await list_subagent_snapshots(
        database_agent_turns=api_context.dependencies.database_agent_turns,
        task_registry_queries=api_context.dependencies.task_registry_queries,
        token_collection=api_context.dependencies.token_collection,
        conv_id=conv_id,
        user_id=user_id,
        parent_turn_id=turn_snapshot.turn_id,
        statuses=frozenset(
            {
                SUBAGENT_STATUS_RUNNING,
                SUBAGENT_STATUS_COMPLETED,
                SUBAGENT_STATUS_CANCELLED,
                SUBAGENT_STATUS_ERROR,
                SUBAGENT_STATUS_MAX_ITERATIONS,
                SUBAGENT_STATUS_ABANDONED,
            },
        ),
    )
    return build_agent_checkpoint_payload(
        snapshot=turn_snapshot,
        subagent_snapshots=subagent_snapshots,
    )


async def snapshot_webui_chat_agent_checkpoint(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    conv_id, user_id = _require_snapshot_conversation_id(data, connection)
    resolved_conv_id = await _require_existing_conversation(
        api_context=connection.api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    return await _build_checkpoint_payload(
        api_context=connection.api_context,
        conv_id=resolved_conv_id,
        user_id=user_id,
    )


async def snapshot_webui_chat_agent_plan(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    conv_id, user_id = _require_snapshot_conversation_id(data, connection)
    resolved_conv_id = await _require_existing_conversation(
        api_context=connection.api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    return await read_agent_plan_payload(
        database_agent_plan=connection.api_context.dependencies.database_agent_plan,
        conv_id=resolved_conv_id,
        user_id=user_id,
    )


async def snapshot_webui_chat_agent_todo(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    conv_id, user_id = _require_snapshot_conversation_id(data, connection)
    resolved_conv_id = await _require_existing_conversation(
        api_context=connection.api_context,
        conv_id=conv_id,
        user_id=user_id,
    )
    return await read_agent_todo_payload(
        database_agent_todo_state=connection.api_context.dependencies.database_agent_todo_state,
        conv_id=resolved_conv_id,
        user_id=user_id,
    )

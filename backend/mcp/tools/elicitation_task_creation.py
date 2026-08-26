"""SoAI - MCP elicitation task creation helpers [backend/mcp/tools/elicitation_task_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.conversations.interaction_checkpoint import (
    build_conversation_interaction_checkpoint,
)
from core.errors.exceptions import StateError
from core.runtime.soai_identifiers import build_soai_id
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.errors import TaskIDCollisionError
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("build_mcp_elicitation_task_id", "ensure_mcp_elicitation_task")


def build_mcp_elicitation_task_id(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    conv_id: str,
    interaction_type: str,
) -> str:
    tool_identity = utility_tools.active_tool_call_context.get()
    if tool_identity is None:
        raise StateError("Conversation elicitation requires an active tool execution context.")
    if tool_identity.turn_id is None or tool_identity.iteration_index is None:
        raise StateError("Conversation elicitation requires an agent turn checkpoint.")
    identity_seed = (
        f"{conv_id}:{tool_identity.turn_id}:{tool_identity.iteration_index}:"
        f"{tool_identity.call_id}:{interaction_type}"
    )
    return f"elicitation_{hashlib.sha256(identity_seed.encode()).hexdigest()[:20]}"


async def ensure_mcp_elicitation_task(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    conv_id: str,
    interaction_type: str,
    suspension_phase: str,
    metadata: JSONDict,
    user_interaction_timeout_ms: int,
) -> Task:
    resolved_conv_id = str(conv_id or "").strip()
    resolved_interaction_type = str(interaction_type or "").strip()
    request_context = utility_tools.active_request_context.get()
    tool_identity = utility_tools.active_tool_call_context.get()
    if request_context is None or tool_identity is None:
        raise StateError("Conversation elicitation requires an active tool execution context.")
    if tool_identity.turn_id is None or tool_identity.iteration_index is None:
        raise StateError("Conversation elicitation requires an agent turn checkpoint.")
    task_id = build_mcp_elicitation_task_id(
        utility_tools,
        conv_id=resolved_conv_id,
        interaction_type=resolved_interaction_type,
    )
    cancellation_id = build_soai_id(
        (
            "task",
            "conversation",
            resolved_conv_id,
            "elicitation",
            resolved_interaction_type,
            task_id,
        ),
    )
    checkpoint = build_conversation_interaction_checkpoint(
        request_context,
        interaction_type=resolved_interaction_type,
        suspension_phase=suspension_phase,
        conv_id=resolved_conv_id,
        iteration_index=tool_identity.iteration_index,
        turn_id=tool_identity.turn_id,
        tool_call_id=tool_identity.call_id,
        tool_arguments=None,
        user_interaction_timeout_ms=user_interaction_timeout_ms,
    )
    try:
        return await create(
            utility_tools.task_registry,
            task_type=TASK_TYPE_MCP_ELICITATION,
            user_id=int(user_id),
            owner_id=resolved_conv_id,
            owner_type="conversation",
            task_id=task_id,
            cancellation_id=cancellation_id,
            status=TaskStatus.INPUT_REQUIRED,
            status_message=f"Awaiting user input for {resolved_interaction_type}",
            poll_interval_ms=1000,
            progress_total=100,
            metadata=metadata,
            interaction_checkpoint=checkpoint,
            ttl_ms=user_interaction_timeout_ms,
        )
    except TaskIDCollisionError as exception:
        existing = await utility_tools.task_registry.get(task_id, force_refresh=True)
        if existing is None:
            raise StateError("Conversation elicitation task replay is unavailable.") from exception
        if (
            existing.user_id != int(user_id)
            or existing.owner_id != resolved_conv_id
            or existing.metadata.get("interaction_type") != resolved_interaction_type
        ):
            raise StateError("Conversation elicitation task identity collided.") from exception
        return existing

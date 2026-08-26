"""SoAI - Durable conversation interaction checkpoint contract [backend/core/conversations/interaction_checkpoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import secrets

from core.database.task_requests import ConversationInteractionCheckpointRequest
from core.errors.exceptions import StateError
from core.runtime.request_context import RequestContext
from core.tasks.protocols_registry import TaskRegistryProtocol
from core.timing.epoch import epoch_ms

__all__ = (
    "ConversationInputSuspended",
    "build_conversation_interaction_checkpoint",
    "raise_if_conversation_input_suspended",
)


class ConversationInputSuspended(BaseException):
    def __init__(self, input_id: str, task_id: str) -> None:
        super().__init__(input_id, task_id)
        self.input_id = input_id
        self.task_id = task_id


def build_conversation_interaction_checkpoint(
    request_context: RequestContext,
    *,
    interaction_type: str,
    suspension_phase: str,
    conv_id: str,
    iteration_index: int,
    turn_id: str,
    tool_call_id: str,
    tool_arguments: str | None,
    user_interaction_timeout_ms: int,
) -> ConversationInteractionCheckpointRequest | None:
    input_id = request_context.conversation_input_id
    if input_id is None:
        return None
    claim_generation = request_context.conversation_input_claim_generation
    claim_owner = request_context.conversation_input_claim_owner
    server_boot_id = request_context.conversation_input_server_boot_id
    if (
        claim_generation is None
        or claim_generation <= 0
        or claim_owner is None
        or server_boot_id is None
    ):
        raise StateError("Conversation interaction requires a complete durable input claim.")
    normalized_turn_id = turn_id.strip()
    normalized_tool_call_id = tool_call_id.strip()
    if not normalized_turn_id or not normalized_tool_call_id:
        raise StateError("Conversation interaction requires exact agent and tool identities.")
    argument_hash = (
        hashlib.sha256(tool_arguments.encode()).hexdigest() if tool_arguments is not None else None
    )
    return ConversationInteractionCheckpointRequest(
        input_id=input_id,
        conv_id=conv_id.strip(),
        user_id=request_context.user_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        interaction_type=interaction_type,
        suspension_phase=suspension_phase,
        iteration_index=iteration_index,
        turn_id=normalized_turn_id,
        tool_call_id=normalized_tool_call_id,
        argument_hash=argument_hash,
        reply_token=secrets.token_hex(3).upper(),
        focus_nonce=secrets.token_urlsafe(24),
        expires_at_ms=epoch_ms() + int(user_interaction_timeout_ms),
    )


async def raise_if_conversation_input_suspended(
    task_registry: TaskRegistryProtocol,
    *,
    input_id: str | None,
    task_id: str,
) -> None:
    if input_id is None:
        return
    suspended = await task_registry.database_tasks.has_conversation_interaction_checkpoint(
        input_id=input_id,
        task_id=task_id,
    )
    if suspended:
        raise ConversationInputSuspended(input_id, task_id)

"""SoAI - Durable Chat input runtime construction [backend/features/chat/conversation_input_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
)
from core.conversations.conversation_input_finalization import (
    ConversationInputFinalization,
)
from core.errors.exceptions import ConflictError, StateError
from core.runtime.cancellation_ids import build_chat_stream_task_cancellation_id
from core.runtime.request_context import RequestContext
from core.runtime.soai_identifiers import create_system_id
from core.types.json import JSONDict
from core.validation.integers import is_non_negative_strict_int, is_strict_int
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.runtime_construction import create_chat_stream_runtime

if TYPE_CHECKING:
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "ConversationInputRuntime",
    "create_conversation_input_runtime",
    "require_conversation_input_identity",
)


@dataclass(frozen=True, slots=True)
class ConversationInputRuntime:
    input_id: str
    conv_id: str
    user_id: int
    claim_generation: int
    model_settings: JSONDict
    request_context: RequestContext
    timeline: AssistantTimelineRuntime


def require_conversation_input_identity(
    input_record: JSONDict,
) -> tuple[str, str, int, int]:
    input_id = input_record.get("input_id")
    conv_id = input_record.get("conv_id")
    user_id = input_record.get("user_id")
    claim_generation = input_record.get("claim_generation")
    if not isinstance(input_id, str) or not input_id.strip():
        raise StateError("Claimed conversation input id is invalid.")
    if not isinstance(conv_id, str) or not conv_id.strip():
        raise StateError("Claimed conversation id is invalid.")
    if not is_strict_int(user_id) or user_id <= 0:
        raise StateError("Claimed conversation input owner is invalid.")
    if not is_non_negative_strict_int(claim_generation) or claim_generation <= 0:
        raise StateError("Claimed conversation input generation is invalid.")
    return (input_id, conv_id, int(user_id), int(claim_generation))


async def _resolve_message_count(
    api_dependencies: ApiDependencies,
    *,
    conv_id: str,
    user_id: int,
) -> int:
    message_count = await api_dependencies.database_messages.count_messages(conv_id, user_id)
    if not is_non_negative_strict_int(message_count):
        raise StateError("Conversation input message count is unavailable.")
    return int(message_count)


async def create_conversation_input_runtime(
    api_dependencies: ApiDependencies,
    *,
    input_record: JSONDict,
    claim_owner: str,
    server_boot_id: str,
) -> ConversationInputRuntime:
    input_id, conv_id, user_id, claim_generation = require_conversation_input_identity(
        input_record,
    )
    if input_record.get("input_type") not in {"prompt", "steer"}:
        raise StateError("Conversation input executor requires a prompt or steer input.")
    model_settings = input_record.get("model_settings")
    request_id = input_record.get("request_id")
    assistant_at_ms = input_record.get("assistant_at_ms")
    assistant_turn_at_ms = input_record.get("assistant_turn_at_ms")
    model_variant_index = input_record.get("model_variant_index")
    final_planned_variant = input_record.get("final_planned_variant")
    if not isinstance(model_settings, dict):
        raise StateError("Conversation input model settings snapshot is unavailable.")
    if not isinstance(request_id, str) or not request_id.strip():
        raise StateError("Conversation input request id is unavailable.")
    if not is_non_negative_strict_int(assistant_at_ms):
        raise StateError("Conversation input assistant timestamp is invalid.")
    if not is_non_negative_strict_int(assistant_turn_at_ms):
        raise StateError("Conversation input assistant turn timestamp is invalid.")
    if not is_non_negative_strict_int(model_variant_index):
        raise StateError("Conversation input model variant index is invalid.")
    if not isinstance(final_planned_variant, bool):
        raise StateError("Conversation input final variant identity is invalid.")
    context_cancellation_id = create_system_id(
        subsystem="conversation_input",
        owner=input_id,
        include_random_suffix=False,
    )
    suspension_phase_value = input_record.get("suspension_phase")
    suspension_task_id_value = input_record.get("task_id")
    suspension_tool_call_id_value = input_record.get("suspension_tool_call_id")
    suspension_generation_value = input_record.get("suspension_generation")
    agent_turn_id_value = input_record.get("agent_turn_id")
    suspension_iteration_value = input_record.get("suspension_iteration")
    request_context = RequestContext(
        trace_id=context_cancellation_id,
        client_ip="internal",
        user_id=user_id,
        task_id=input_id,
        cancellation_id=context_cancellation_id,
        interactive_tool_approval=True,
        conversation_input_id=input_id,
        conversation_input_claim_generation=claim_generation,
        conversation_input_claim_owner=claim_owner,
        conversation_input_server_boot_id=server_boot_id,
        conversation_input_resume_phase=(
            suspension_phase_value if isinstance(suspension_phase_value, str) else None
        ),
        conversation_input_resume_task_id=(
            suspension_task_id_value if isinstance(suspension_task_id_value, str) else None
        ),
        conversation_input_resume_tool_call_id=(
            suspension_tool_call_id_value
            if isinstance(suspension_tool_call_id_value, str)
            else None
        ),
        conversation_input_resume_generation=(
            int(suspension_generation_value)
            if is_non_negative_strict_int(suspension_generation_value)
            else None
        ),
        agent_turn_id=(agent_turn_id_value if isinstance(agent_turn_id_value, str) else None),
        agent_iteration_index=(
            int(suspension_iteration_value)
            if is_non_negative_strict_int(suspension_iteration_value)
            else None
        ),
    )
    task_cancellation_id = build_chat_stream_task_cancellation_id(
        context_cancellation_id=context_cancellation_id,
        request_id=request_id,
    )

    async def require_input_claim() -> None:
        await api_dependencies.database_input_execution.require_active_claim(
            input_id=input_id,
            claim_generation=claim_generation,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
        )

    model_value = model_settings.get("model")
    timeline = create_chat_stream_runtime(
        conv_id=conv_id,
        request_id=request_id,
        identity=AssistantTurnVariantIdentity(
            assistant_at_ms=int(assistant_at_ms),
            assistant_turn_at_ms=int(assistant_turn_at_ms),
            model_variant_index=int(model_variant_index),
        ),
        user_id=user_id,
        message_index=await _resolve_message_count(
            api_dependencies,
            conv_id=conv_id,
            user_id=user_id,
        ),
        model_id=model_value if isinstance(model_value, str) else None,
        task_cancellation_id=task_cancellation_id,
        mutation_guard=require_input_claim,
    )
    timeline.input_finalization = ConversationInputFinalization(
        input_id=input_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        final_planned_variant=final_planned_variant,
    )
    if not await api_dependencies.chat_stream_registry.try_register(timeline):
        raise ConflictError("Conversation input stream registration failed.")
    return ConversationInputRuntime(
        input_id=input_id,
        conv_id=conv_id,
        user_id=user_id,
        claim_generation=claim_generation,
        model_settings=model_settings,
        request_context=request_context,
        timeline=timeline,
    )

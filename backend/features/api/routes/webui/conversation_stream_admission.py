"""SoAI - Conversation stream admission resolution [backend/features/api/routes/webui/conversation_stream_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ConflictError
from features.api.runtime.chat_stream_registry import ChatStreamRegistrySnapshot

if TYPE_CHECKING:
    from core.conversations.conversation_input_active_state import ActiveConversationInputSummary

__all__ = (
    "ConversationStreamAdmission",
    "require_input_queue_enqueue_admitted",
    "resolve_conversation_stream_admission",
)


@dataclass(frozen=True, slots=True)
class ConversationStreamAdmission:
    active: bool
    start_admission: Literal["inactive", "busy", "unknown"]
    stream_lifecycle: Literal["inactive", "streaming", "terminalizing"]
    can_accept_conversation_input: bool
    can_start_next_prompt: bool
    can_accept_queued_prompt: bool
    can_accept_steer_prompt: bool


def _resolve_inactive_admission(
    *,
    active_input_summary: ActiveConversationInputSummary,
    reserved: bool,
) -> ConversationStreamAdmission:
    busy = active_input_summary.has_active_inputs or reserved
    return ConversationStreamAdmission(
        active=False,
        start_admission="busy" if busy else "inactive",
        stream_lifecycle="inactive",
        can_accept_conversation_input=busy,
        can_start_next_prompt=not busy,
        can_accept_queued_prompt=busy,
        can_accept_steer_prompt=False,
    )


def resolve_conversation_stream_admission(
    snapshot: ChatStreamRegistrySnapshot,
    *,
    active_input_summary: ActiveConversationInputSummary,
    user_interaction_pending: bool,
) -> ConversationStreamAdmission:
    runtime = snapshot.runtime
    if runtime is None or runtime.terminal_persistence_completed:
        return _resolve_inactive_admission(
            active_input_summary=active_input_summary,
            reserved=snapshot.reservation is not None,
        )
    stream_lifecycle: Literal["streaming", "terminalizing"] = (
        "terminalizing" if runtime.terminal_finalization_started else "streaming"
    )
    return ConversationStreamAdmission(
        active=True,
        start_admission="busy",
        stream_lifecycle=stream_lifecycle,
        can_accept_conversation_input=True,
        can_start_next_prompt=False,
        can_accept_queued_prompt=True,
        can_accept_steer_prompt=stream_lifecycle == "streaming" and not user_interaction_pending,
    )


def require_input_queue_enqueue_admitted(
    admission: ConversationStreamAdmission,
    intent: Literal["queued", "steer"],
) -> None:
    if intent == "queued" and admission.can_accept_queued_prompt:
        return
    if intent == "steer" and admission.can_accept_steer_prompt:
        return
    if intent == "steer" and admission.stream_lifecycle == "terminalizing":
        raise ConflictError("Cannot steer a stream that is already terminalizing.")
    raise ConflictError("Input queue enqueue requires an active conversation stream.")

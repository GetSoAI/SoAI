"""SoAI - Durable agent inference prompt replay contracts [backend/core/agent/prompt_replay.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.chat_messages_contracts import (
    extract_expected_tool_call_ids,
    validate_internal_chat_messages_contracts,
)
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_dict, parse_json_value
from core.types.json_value import require_json_dict_list

if TYPE_CHECKING:
    from core.conversations.assistant_turn_variant_identity import AssistantTurnVariantIdentity
    from core.skills.checkpoint import SkillActivationCheckpoint
    from core.types.json import JSONDict

__all__ = ("AgentInferencePromptReplay", "AgentTurnPromptReplaySnapshot")


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentInferencePromptReplay:
    assistant_tool_message_json: str | None
    following_messages_json: str | None

    def __post_init__(self) -> None:
        assistant = (
            parse_json_dict(self.assistant_tool_message_json, field="agent replay assistant")
            if self.assistant_tool_message_json is not None
            else None
        )
        if assistant is not None:
            if assistant.get("role") != "assistant" or not extract_expected_tool_call_ids(
                assistant.get("tool_calls"),
                message_index=0,
            ):
                raise ValidationError("Agent replay requires an assistant tool-call message.")
            reasoning = assistant.get("reasoning_content")
            if reasoning is not None and not isinstance(reasoning, str):
                raise ValidationError("Agent replay reasoning must be text.")
        if self.following_messages_json is None:
            if assistant is None:
                raise ValidationError("Pending agent replay requires tool calls.")
            return
        following = require_json_dict_list(
            parse_json_value(self.following_messages_json, field="agent replay following messages"),
            label="Agent replay following messages",
        )
        messages = [*([assistant] if assistant is not None else []), *following]
        validate_internal_chat_messages_contracts({"messages": messages})

    @classmethod
    def from_messages(
        cls,
        *,
        messages: Sequence[JSONDict],
        pending: bool = False,
    ) -> AgentInferencePromptReplay:
        assistant = (
            messages[0]
            if messages and messages[0].get("role") == "assistant" and messages[0].get("tool_calls")
            else None
        )
        following = messages[1:] if assistant is not None else messages
        return cls(
            assistant_tool_message_json=(
                serialize_json_compact_stable(assistant) if assistant is not None else None
            ),
            following_messages_json=(
                None if pending else serialize_json_compact_stable(list(following))
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentTurnPromptReplaySnapshot:
    checkpoint_json: str
    latest_replay_json: str | None
    history_messages_json: str
    pending_reasoning_text: str
    identity: AssistantTurnVariantIdentity
    claimed_execution_token: str | None = None
    skill_activation: SkillActivationCheckpoint | None = None

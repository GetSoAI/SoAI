"""SoAI - Durable conversation input quota reservation [backend/features/chat/conversation_input_quota_reservation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import RateLimitError
from features.api.runtime.chat_execution.quota import (
    ConversationTurnQuotaDenied,
    ConversationTurnQuotaReservation,
    reserve_conversation_turn_stream_quota,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime
    from features.chat.conversation_input_turn_preparation import (
        PreparedConversationInputTurn,
    )

__all__ = ("reserve_conversation_input_turn_quota",)


async def reserve_conversation_input_turn_quota(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    prepared: PreparedConversationInputTurn,
    runtime: AssistantTimelineRuntime,
    logger: LoggerProtocol,
) -> None:
    quota_result = await reserve_conversation_turn_stream_quota(
        api_dependencies=api_dependencies,
        user_id=user_id,
        request_json=(
            prepared.prepared_agent_request.final_payload
            if prepared.prepared_agent_request is not None
            else prepared.request_json
        ),
        logger=logger,
    )
    if isinstance(quota_result, ConversationTurnQuotaDenied):
        raise RateLimitError(
            quota_result.message,
            details={
                "window": quota_result.window,
                "retry_at_ms": quota_result.retry_at_ms,
            },
        )
    if not isinstance(quota_result, ConversationTurnQuotaReservation):
        return
    runtime.quota_key_id = quota_result.key_id
    runtime.quota_token_reservation = quota_result.token_reservation
    if isinstance(quota_result.token_reservation, dict):
        prompt_tokens = quota_result.token_reservation.get("prompt_tokens")
        if isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool):
            runtime.quota_prompt_tokens = prompt_tokens

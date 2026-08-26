"""SoAI - Non-agent strict retry request and admission [backend/features/api/streaming/assistant_timeline/non_agent/retry_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.request_field_filtering import build_inference_request_payload
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.streaming_inference_admission import (
    AgentStreamingTaskBundle,
    create_streaming_inference_task,
)
from features.api.runtime.chat_execution.quota import (
    ConversationTurnQuotaDenied,
    ConversationTurnQuotaReservation,
    reserve_conversation_turn_quota,
)
from features.api.runtime.chat_execution.runtime_quota import (
    release_locked_ws_chat_stream_runtime_quota_if_present,
)
from features.api.runtime.chat_execution.task_metadata import (
    build_ws_chat_stream_task_metadata,
)
from features.api.runtime.preview_contract_retry import (
    build_preview_contract_retry_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = (
    "build_retry_request_json",
    "create_non_agent_retry_bundle",
)


def build_retry_request_json(
    request_json: JSONDict,
    *,
    assistant_text: str,
    failure_detail: str | None,
) -> JSONDict:
    messages_value = request_json.get("messages")
    if not isinstance(messages_value, list):
        raise ValidationError("Chat stream retry requires request_json.messages to be a list.")
    next_messages = list(messages_value)
    normalized_text = assistant_text.strip()
    if normalized_text:
        next_messages.append(
            {
                "role": "assistant",
                "content": normalized_text,
            },
        )
    next_messages.append(build_preview_contract_retry_message(failure_detail))
    return {
        **request_json,
        "messages": next_messages,
    }


async def reserve_retry_quota(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    request_json: JSONDict,
) -> ConversationTurnQuotaDenied | ConversationTurnQuotaReservation | None:
    if user_id <= 0:
        return None
    return await reserve_conversation_turn_quota(
        api_dependencies.database_api_keys,
        user_id,
        request_json=build_inference_request_payload(request_json),
        config=api_dependencies.config,
        prompt_token_counter=api_dependencies.prompt_token_counter,
    )


async def create_non_agent_retry_bundle(
    api_dependencies: ApiDependencies,
    *,
    context: RequestContext,
    session: AssistantTimelineSession,
    request_json: JSONDict,
) -> AgentStreamingTaskBundle | ConversationTurnQuotaDenied:
    async with session.runtime.quota_release_lock:
        await release_locked_ws_chat_stream_runtime_quota_if_present(
            database_api_keys=api_dependencies.database_api_keys,
            runtime=session.runtime,
            trace_id=context.trace_id,
            operation="webui_ws_chat_stream.retry.release_previous_quota",
        )
        quota_result = await reserve_retry_quota(
            api_dependencies,
            user_id=session.runtime.user_id,
            request_json=request_json,
        )
        if isinstance(quota_result, ConversationTurnQuotaDenied):
            return quota_result
        if isinstance(quota_result, ConversationTurnQuotaReservation):
            session.runtime.quota_key_id = quota_result.key_id
            session.runtime.quota_token_reservation = quota_result.token_reservation
            if isinstance(quota_result.token_reservation, dict):
                prompt_tokens_value = quota_result.token_reservation.get("prompt_tokens")
                if isinstance(prompt_tokens_value, int) and not isinstance(
                    prompt_tokens_value,
                    bool,
                ):
                    session.runtime.quota_prompt_tokens = prompt_tokens_value
        bundle = await create_streaming_inference_task(
            api_dependencies,
            context=context,
            request_json=request_json,
            task_type=TASK_TYPE_CHAT_COMPLETION,
            user_id=session.runtime.user_id,
            owner_type="conversation",
            owner_id=session.runtime.conv_id,
            cancellation_id=session.runtime.task_cancellation_id,
            metadata=build_ws_chat_stream_task_metadata(runtime=session.runtime),
            request_source=REQUEST_SOURCE_WEBUI_WS,
        )
        session.runtime.active_task_id = bundle.task.task_id
        session.runtime.clear_quota_reservation()
    return bundle

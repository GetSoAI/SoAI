"""SoAI - Auto-title inference execution [backend/features/api/conversation_auto_title/inference.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import zlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from core.conversations.default_title_resolution import resolve_first_text_content_part
from core.errors.exceptions import StateError
from core.events.types_models_requests import InferenceRequestReceived
from core.prompts.system_prompts import get_text_prompt_v1
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import REQUEST_SOURCE_SYSTEM
from core.runtime.soai_identifiers import create_request_id, create_system_id
from core.validation.integers import is_strict_int
from features.api.conversation_auto_title.prompt_template import build_auto_title_prompt
from features.api.conversation_auto_title.title_parser import parse_auto_title
from features.api.routes.openai.chat.non_streaming.runner import (
    wait_for_non_streaming_inference_result,
)
from features.api.routes.openai.chat.task_acceptance import accept_chat_inference_task
from features.api.runtime.openai_execution.contracts import InferenceQuotaContext
from features.api.runtime.response_body import parse_response_body_json_dict
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies

__all__ = (
    "acquire_auto_title_slot",
    "generate_auto_title",
    "parse_auto_title_response",
)

_AUTO_TITLE_GENERATION_SLOT_BASE = -91001
_AUTO_TITLE_GENERATION_SLOT_COUNT = 2
_AUTO_TITLE_TIMEOUT_SECONDS = 18.0


@dataclass(frozen=True, slots=True)
class AutoTitleApiContext:
    dependencies: ApiDependencies


@asynccontextmanager
async def acquire_auto_title_slot(
    api_dependencies: ApiDependencies,
    *,
    conversation_id: str,
) -> AsyncGenerator[None]:
    prompts_update_locks = api_dependencies.prompts_update_locks
    normalized_conversation_id = conversation_id.strip()
    if not normalized_conversation_id:
        raise StateError("Auto-title generation requires a conversation id.")
    async with prompts_update_locks.lock(_resolve_auto_title_slot_key(normalized_conversation_id)):
        yield


def _resolve_auto_title_slot_key(conversation_id: str) -> int:
    slot_index = zlib.crc32(conversation_id.encode("utf-8")) % _AUTO_TITLE_GENERATION_SLOT_COUNT
    return _AUTO_TITLE_GENERATION_SLOT_BASE - slot_index


async def generate_auto_title(
    *,
    api_dependencies: ApiDependencies,
    runtime: AssistantTimelineRuntime,
    user_message: JSONDict,
    assistant_message: JSONDict,
) -> str | None:
    context_window_tokens = runtime.usage_preview_context_window_tokens
    if not is_strict_int(context_window_tokens) or context_window_tokens <= 0:
        return None
    api_context = AutoTitleApiContext(dependencies=api_dependencies)
    request_context = RequestContext(
        trace_id=create_request_id(prefix="auto-title"),
        client_ip="internal",
        user_id=runtime.user_id,
        cancellation_id=create_system_id(
            subsystem="conversation_auto_title",
            owner=runtime.conv_id,
            include_random_suffix=True,
        ),
    )
    payload: JSONDict = {
        "model": runtime.model_id,
        "messages": [
            {
                "role": "system",
                "content": get_text_prompt_v1("conversation.auto_title.system.v1"),
            },
            {
                "role": "user",
                "content": build_auto_title_prompt(
                    user_message=user_message,
                    assistant_message=assistant_message,
                ),
            },
        ],
        "stream": False,
        "max_tokens": 80,
        "temperature": 0.2,
        "timeout": 15,
        "reasoning_effort": "none",
        "context_window_tokens": context_window_tokens,
    }
    quota = InferenceQuotaContext(
        api_context=api_context,
        key_id=None,
        reservation=None,
        trace_id=request_context.trace_id,
        operation_prefix="conversation_auto_title",
    )
    stream_dependencies = build_stream_dependencies(api_dependencies)
    async with asyncio.timeout(_AUTO_TITLE_TIMEOUT_SECONDS):
        task, reply_queue = await accept_chat_inference_task(
            api_context=api_context,
            context=request_context,
            quota=quota,
            metrics_manager=api_dependencies.metrics_manager,
            request_event_class=InferenceRequestReceived,
            user_id=runtime.user_id,
            owner_type="conversation",
            owner_id=runtime.conv_id,
            cancellation_id=request_context.cancellation_id,
            metadata={"internal_operation": "conversation_auto_title"},
            payload=payload,
            required_capabilities=(),
            required_modalities=(),
            async_accept_requested=False,
            is_streaming=False,
            request_source=REQUEST_SOURCE_SYSTEM,
        )
        if reply_queue is None:
            raise StateError("Auto-title inference did not return a reply queue.")
        response = await wait_for_non_streaming_inference_result(
            api_context,
            stream_dependencies=stream_dependencies,
            registry=api_dependencies.task_registry,
            task=task,
            reply_queue=reply_queue,
            context=request_context,
            request_json=payload,
            required_capabilities=(),
        )
    return parse_auto_title_response(response)


def parse_auto_title_response(response: JSONResponse) -> str | None:
    if response.status_code < 200 or response.status_code >= 300:
        return None
    payload = parse_response_body_json_dict(
        response,
        field="auto title completion response",
    )
    choices_value = payload.get("choices")
    if not isinstance(choices_value, list) or not choices_value:
        return None
    choice = choices_value[0]
    if not isinstance(choice, dict):
        return None
    message = choice.get("message")
    if not isinstance(message, dict):
        return None
    content_text = resolve_first_text_content_part(message.get("content"))
    if content_text is None:
        return None
    return parse_auto_title(content_text)

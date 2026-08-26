"""SoAI - Manual compaction summarizer pipeline [backend/features/api/routes/webui/conversation_agent_compaction/summarizer_pipeline.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial

from fastapi import Request

from core.errors.exceptions import ValidationError
from core.openai.pinned_prefix import strip_leading_pinned_prefix
from core.openai.token_accounting import count_prompt_occupancy_async
from core.prompts.system_prompts import get_compaction_summary_system_text_v1
from core.runtime.request_context import RequestContext
from core.serialization.json import serialize_json_compact_stable
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from core.tool_calls.context_compaction_boundary_resolution import (
    resolve_context_compaction_boundaries,
)
from core.types.json import JSONDict
from features.agent.runtime.context_compaction.summary import build_summary_message
from features.api.routes.openai.compaction.summarizer import (
    prepare_agent_compaction_summarizer,
)
from features.api.routes.webui.conversation_agent_compaction.context import (
    coerce_compaction_history,
    resolve_manual_target_prompt_tokens,
)
from features.api.routes.webui.conversation_agent_compaction.summary import (
    truncate_summary_to_budget,
)
from features.api.runtime.context import ApiContext
from features.api.streaming.types import StreamDependencies

__all__ = (
    "ManualCompactionSummaryResult",
    "build_manual_compaction_summary_text",
)


@dataclass(frozen=True, slots=True)
class ManualCompactionSummaryResult:
    summary_text: str
    prompt_message: JSONDict
    source_prompt_tokens: int
    target_prompt_tokens: int
    summary_prompt_tokens: int
    source_message_count: int
    source_serialized_chars: int
    summary_chars: int


async def build_manual_compaction_summary_text(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    conv_id: str,
    model: str,
    source_messages: list[JSONDict],
    compaction_limit: int | None,
    summarizer_budget: int,
    raise_if_cancelled: Callable[[], Awaitable[None]],
    on_text_delta: Callable[[str], Awaitable[None]],
) -> ManualCompactionSummaryResult:
    await raise_if_cancelled()
    source_message_body = strip_leading_pinned_prefix(source_messages)
    boundary_resolution = resolve_context_compaction_boundaries(
        source_message_body,
        strip_leading_pinned_prefix=False,
    )
    effective_source_messages = boundary_resolution.messages
    message_history = coerce_compaction_history(effective_source_messages)
    current_payload: JSONDict = {"model": model, "messages": list(message_history)}
    current_occupancy = await count_prompt_occupancy_async(
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        request_payload=current_payload,
    )
    current_prompt_tokens = current_occupancy.prompt_tokens
    target_prompt_tokens = resolve_manual_target_prompt_tokens(
        current_prompt_tokens=int(current_prompt_tokens),
        configured_limit=compaction_limit,
    )
    await raise_if_cancelled()

    summarize_messages = prepare_agent_compaction_summarizer(
        request=request,
        api_context=api_context,
        stream_dependencies=stream_dependencies,
        context=context,
        model=model,
        system_prompt_text=get_compaction_summary_system_text_v1(),
        task_type=TASK_TYPE_CHAT_COMPLETION,
        owner_type="conversation",
        owner_id=conv_id,
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        max_prompt_tokens=summarizer_budget,
        on_text_delta=on_text_delta,
    )
    await raise_if_cancelled()
    summary_text = (await summarize_messages(message_history)).strip()
    if not summary_text:
        raise ValidationError("Context compaction summarizer returned an empty response.")
    await raise_if_cancelled()
    truncated_summary_text = await api_context.dependencies.prompt_token_counter.run_blocking(
        partial(
            truncate_summary_to_budget,
            api_context=api_context,
            model=model,
            summary_text=summary_text,
            target_prompt_tokens=target_prompt_tokens,
        ),
    )
    prompt_message = build_summary_message(truncated_summary_text)
    summary_payload: JSONDict = {
        "model": model,
        "messages": [prompt_message],
    }
    summary_occupancy = await count_prompt_occupancy_async(
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        request_payload=summary_payload,
    )
    summary_prompt_tokens = summary_occupancy.prompt_tokens
    source_serialized_chars = len(
        serialize_json_compact_stable(message_history, ensure_ascii=False),
    )
    summary_chars = len(truncated_summary_text)
    return ManualCompactionSummaryResult(
        summary_text=truncated_summary_text,
        prompt_message=prompt_message,
        source_prompt_tokens=int(current_prompt_tokens),
        target_prompt_tokens=int(target_prompt_tokens),
        summary_prompt_tokens=int(summary_prompt_tokens),
        source_message_count=len(effective_source_messages),
        source_serialized_chars=int(source_serialized_chars),
        summary_chars=int(summary_chars),
    )

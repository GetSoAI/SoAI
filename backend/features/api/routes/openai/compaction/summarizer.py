"""SoAI - Agent context compaction summarizer [backend/features/api/routes/openai/compaction/summarizer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from core.errors.exceptions import ApiError, ValidationError
from core.openai.internal_retry_prompt import build_internal_retry_user_message
from core.openai.token_accounting import count_prompt_occupancy
from core.runtime.protocols import RequestProtocol
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.tasks.type_catalog import TaskTypeId
from features.agent.runtime.context_compaction.omission_digest import (
    render_omitted_messages_digest,
)
from features.agent.session.compaction_config_values import (
    resolve_compaction_summary_max_tokens,
)
from features.agent.session.compaction_limits import AGENT_SUMMARIZER_MAX_MESSAGES
from features.api.routes.openai.agent_inference_task_creation import (
    create_agent_inference_task,
)
from features.api.routes.openai.chat.chat_ops import (
    get_effective_routing_config,
    resolve_non_streaming_timeout,
)
from features.api.routes.openai.compaction.content import project_message_for_summary
from features.api.routes.openai.compaction.payload import build_summary_payload
from features.api.routes.openai.compaction.streaming import (
    await_streaming_summary_text,
    resolve_summary_cancellation_id,
)
from features.api.routes.openai.compaction.truncation import (
    prepare_messages_for_summary,
)
from features.api.routes.openai.hidden_streaming_text import (
    HiddenStreamingEmptyResponseError,
)
from features.api.runtime.context import ApiContext
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict

__all__ = ("prepare_agent_compaction_summarizer",)

COMPACTION_NO_REASONING_RETRY_ERROR = (
    "Context compaction summarizer failed after no-reasoning retry."
)


def _build_visible_output_retry_message() -> JSONDict:
    return build_internal_retry_user_message(
        "Return the summary now as normal visible assistant text. Do not output hidden reasoning, chain-of-thought, or meta-analysis. Do not include sections such as Thinking Process. Use the required summary structure only. Return only the corrected summary.",
    )


def prepare_agent_compaction_summarizer(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    model: str,
    system_prompt_text: str,
    task_type: TaskTypeId,
    owner_type: str,
    owner_id: str,
    prompt_token_counter: PromptTokenCounter,
    max_prompt_tokens: int,
    on_text_delta: Callable[[str], Awaitable[None]] | None,
) -> Callable[[list[JSONDict]], Awaitable[str]]:
    resolved_max = int(max_prompt_tokens)
    if resolved_max < 1:
        raise ValidationError("compaction summarizer max_prompt_tokens must be >= 1.")
    prompt_text = str(system_prompt_text or "").strip()
    if not prompt_text:
        raise ValidationError("compaction system_prompt_text must be a non-empty string.")
    timeout = resolve_non_streaming_timeout(get_effective_routing_config(api_context), None)
    summary_max_tokens = resolve_compaction_summary_max_tokens(api_context.dependencies.config)

    def _count_summary_prompt_tokens_result(chunk: list[JSONDict]) -> tuple[int, bool]:
        payload = build_summary_payload(
            model=model,
            system_prompt_text=prompt_text,
            chunk=chunk,
            max_output_tokens=summary_max_tokens,
        )
        occupancy = count_prompt_occupancy(
            prompt_token_counter=prompt_token_counter,
            request_payload=payload,
        )
        return occupancy.prompt_tokens, bool(occupancy.capped)

    def _resolve_kept_start_index(prepared_messages: list[JSONDict]) -> int:
        if not prepared_messages:
            raise ValidationError(
                "Context compaction summarizer received no messages to summarize.",
            )
        low = 0
        high = len(prepared_messages) - 1
        best = len(prepared_messages)
        while low <= high:
            mid = (low + high) // 2
            tokens, capped = _count_summary_prompt_tokens_result(prepared_messages[mid:])
            if not capped and tokens <= resolved_max:
                best = mid
                high = mid - 1
                continue
            low = mid + 1
        if best >= len(prepared_messages):
            raise ValidationError(
                "Unable to summarize: compaction token budget is too small to allocate a chunk.",
            )
        return best

    async def _summarize_once(chunk: list[JSONDict]) -> str:
        async def _run_summary_request(
            summary_chunk: list[JSONDict],
            *,
            disable_reasoning: bool,
        ) -> str:
            task_context = clone_request_context(context, task_id=None)
            payload = build_summary_payload(
                model=model,
                system_prompt_text=prompt_text,
                chunk=summary_chunk,
                max_output_tokens=summary_max_tokens,
                disable_reasoning=disable_reasoning,
            )
            task_bundle = await create_agent_inference_task(
                request,
                api_context,
                context=task_context,
                payload=payload,
                task_type=task_type,
                owner_type=owner_type,
                owner_id=owner_id,
                cancellation_id=resolve_summary_cancellation_id(task_context),
                event_type_label="agentic_compaction",
            )
            stream_context = clone_request_context(
                context,
                task_id=task_bundle.task.task_id,
            )
            summary_text = await await_streaming_summary_text(
                request=request,
                context=stream_context,
                stream_dependencies=stream_dependencies,
                request_json=task_bundle.payload,
                reply_queue=task_bundle.reply_queue,
                task_id=task_bundle.task.task_id,
                timeout=timeout,
                on_text_delta=on_text_delta,
            )
            if not summary_text:
                raise ValidationError("Context compaction summarizer returned an empty response.")
            return summary_text

        try:
            summary_text = await _run_summary_request(chunk, disable_reasoning=False)
        except HiddenStreamingEmptyResponseError:
            retry_chunk = list(chunk)
            retry_chunk.append(_build_visible_output_retry_message())
        else:
            return summary_text
        try:
            return await _run_summary_request(retry_chunk, disable_reasoning=True)
        except (ApiError, ValidationError) as exception:
            raise ValidationError(COMPACTION_NO_REASONING_RETRY_ERROR) from exception

    async def summarize_messages(messages: list[JSONDict]) -> str:
        normalized_messages = [message for message in messages if isinstance(message, dict)]
        if not normalized_messages:
            raise ValidationError(
                "Context compaction summarizer received no messages to summarize.",
            )
        base_omitted = max(0, len(normalized_messages) - AGENT_SUMMARIZER_MAX_MESSAGES)
        base_dropped_tail: list[JSONDict] = []
        if base_omitted > 0:
            base_dropped_tail = normalized_messages[max(0, base_omitted - 200) : base_omitted]
            normalized_messages = normalized_messages[base_omitted:]
        projected = [project_message_for_summary(message) for message in normalized_messages]
        kept_start = await prompt_token_counter.run_blocking(
            _resolve_kept_start_index,
            projected,
        )
        prepared_kept = await prompt_token_counter.run_blocking(
            partial(
                prepare_messages_for_summary,
                prompt_token_counter=prompt_token_counter,
                model=model,
                system_prompt_text=prompt_text,
                messages=normalized_messages[kept_start:],
                max_prompt_tokens=resolved_max,
                max_output_tokens=summary_max_tokens,
            ),
        )
        kept_tokens, kept_capped = await prompt_token_counter.run_blocking(
            _count_summary_prompt_tokens_result,
            prepared_kept,
        )
        if kept_capped or kept_tokens > resolved_max:
            extra_drop = await prompt_token_counter.run_blocking(
                _resolve_kept_start_index,
                prepared_kept,
            )
            kept_start += extra_drop
            prepared_kept = prepared_kept[extra_drop:]
        omitted_total = base_omitted + kept_start
        dropped_for_digest = list(base_dropped_tail)
        if kept_start > 0:
            dropped_for_digest.extend(normalized_messages[:kept_start])
        overflow_digest = render_omitted_messages_digest(
            dropped=dropped_for_digest,
            omitted_count=omitted_total,
        )
        llm_summary = await _summarize_once(prepared_kept)
        combined = (
            f"{overflow_digest}\n\n{llm_summary}".strip()
            if overflow_digest is not None
            else llm_summary.strip()
        )
        if not combined:
            raise ValidationError("Context compaction summarizer returned an empty response.")
        return combined

    return summarize_messages

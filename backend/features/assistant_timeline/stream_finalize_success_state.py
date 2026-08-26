"""SoAI - Shared assistant timeline success finalization state derivation [backend/features/assistant_timeline/stream_finalize_success_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.usage.serialization import (
    extract_public_usage_payload,
    is_aggregate_usage_source,
)
from core.timing.monotonic import monotonic_ms
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from core.validation.strings import coerce_optional_trimmed_str
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.terminal_visible_text import (
    drain_terminal_visible_text,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ChatStreamCanonicalUsage",
    "ChatStreamSuccessSnapshot",
    "collect_chat_stream_success_snapshot",
)


@dataclass(frozen=True, slots=True)
class ChatStreamSuccessSnapshot:
    finish_reason: str | None
    usage: ChatStreamCanonicalUsage | None
    context_usage: ChatStreamCanonicalUsage | None
    pending_visible_text: str
    duration_ms: int
    thinking_tail_duration_ms: int
    has_visible_text: bool
    has_visible_thinking_phase: bool
    has_visible_tool_calls: bool
    has_visible_images: bool
    tool_call_terminal_message: str


@dataclass(frozen=True, slots=True)
class _FinalPayloadState:
    finish_reason: str | None
    usage: ChatStreamCanonicalUsage | None
    context_usage: ChatStreamCanonicalUsage | None


@dataclass(frozen=True, slots=True)
class ChatStreamCanonicalUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    usage_source: str

    def as_public_usage_payload(self) -> JSONDict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "usage_source": self.usage_source,
        }


def _summarize_tool_call_names(tool_calls: list[JSONDict]) -> str | None:
    names: list[str] = []
    seen: set[str] = set()
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        function_value = call.get("function")
        if not isinstance(function_value, dict):
            continue
        name_value = function_value.get("name")
        if not isinstance(name_value, str):
            continue
        normalized_name = name_value.strip()
        if not normalized_name or normalized_name in seen:
            continue
        names.append(normalized_name)
        seen.add(normalized_name)
        if len(names) >= 5:
            break
    if not names:
        return None
    return ", ".join(names)


def _resolve_pending_visible_text(
    *,
    context: ChatStreamFinalizeContext,
) -> str:
    return drain_terminal_visible_text(
        runtime=context.runtime,
        stream_transcript=context.stream_transcript,
    )


def _collect_final_payload_state(
    context: ChatStreamFinalizeContext,
) -> _FinalPayloadState:
    final_payload = context.stream_transcript.build_result_payload()
    finish_reason: str | None = None
    if isinstance(final_payload, dict):
        choices_value = final_payload.get("choices")
        if isinstance(choices_value, list) and choices_value:
            first_choice = choices_value[0]
            if isinstance(first_choice, dict):
                finish_reason_value = first_choice.get("finish_reason")
                if isinstance(finish_reason_value, str):
                    finish_reason = finish_reason_value
    return _FinalPayloadState(
        finish_reason=finish_reason,
        usage=_resolve_aggregate_usage(
            context.runtime.aggregate_usage,
            context.runtime.canonical_usage,
            final_payload=final_payload,
        ),
        context_usage=_resolve_context_usage(
            context.runtime.canonical_usage,
            final_payload=final_payload,
            has_aggregate_usage=context.runtime.aggregate_usage is not None,
        ),
    )


def _coerce_internal_usage(
    usage: JSONDict | None,
    *,
    allow_aggregate: bool,
) -> ChatStreamCanonicalUsage | None:
    if not isinstance(usage, dict):
        return None
    prompt_tokens = coerce_optional_non_negative_int_strict(usage.get("prompt_tokens"))
    completion_tokens = coerce_optional_non_negative_int_strict(usage.get("completion_tokens"))
    total_tokens = coerce_optional_non_negative_int_strict(usage.get("total_tokens"))
    usage_source = usage.get("usage_source")
    if prompt_tokens is None or completion_tokens is None or total_tokens is None:
        return None
    if total_tokens != prompt_tokens + completion_tokens:
        return None
    normalized_usage_source = coerce_optional_trimmed_str(usage_source)
    if normalized_usage_source is None:
        return None
    if not allow_aggregate and is_aggregate_usage_source(normalized_usage_source):
        return None
    return ChatStreamCanonicalUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        usage_source=normalized_usage_source,
    )


def _coerce_public_usage(
    usage_payload: JSONValue,
    *,
    allow_aggregate: bool,
) -> ChatStreamCanonicalUsage | None:
    public_usage = extract_public_usage_payload(usage_payload)
    if public_usage is None:
        return None
    prompt_tokens = coerce_optional_non_negative_int_strict(public_usage.get("prompt_tokens"))
    completion_tokens = coerce_optional_non_negative_int_strict(
        public_usage.get("completion_tokens"),
    )
    total_tokens = coerce_optional_non_negative_int_strict(public_usage.get("total_tokens"))
    if prompt_tokens is None or completion_tokens is None or total_tokens is None:
        return None
    usage_source = None
    if isinstance(usage_payload, dict):
        usage_source = coerce_optional_trimmed_str(usage_payload.get("usage_source"))
    if not allow_aggregate and is_aggregate_usage_source(usage_source):
        return None
    return ChatStreamCanonicalUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        usage_source=usage_source or "provider_reported",
    )


def _resolve_aggregate_usage(
    aggregate_usage: JSONDict | None,
    context_usage: JSONDict | None,
    *,
    final_payload: JSONDict,
) -> ChatStreamCanonicalUsage | None:
    if (
        resolved := _coerce_internal_usage(
            aggregate_usage,
            allow_aggregate=True,
        )
    ) is not None:
        return resolved
    if (
        resolved := _coerce_internal_usage(
            context_usage,
            allow_aggregate=False,
        )
    ) is not None:
        return resolved
    return _coerce_public_usage(final_payload.get("usage"), allow_aggregate=True)


def _resolve_context_usage(
    context_usage: JSONDict | None,
    *,
    final_payload: JSONDict,
    has_aggregate_usage: bool,
) -> ChatStreamCanonicalUsage | None:
    if (
        resolved := _coerce_internal_usage(
            context_usage,
            allow_aggregate=False,
        )
    ) is not None:
        return resolved
    if has_aggregate_usage:
        return None
    return _coerce_public_usage(final_payload.get("usage"), allow_aggregate=False)


def _resolve_terminal_tool_call_message(context: ChatStreamFinalizeContext) -> str:
    tool_call_terminal_message = "Tool call did not complete before the stream finished."
    streamed_tool_calls = context.stream_transcript.get_tool_calls()
    if (
        streamed_tool_calls
        and not context.runtime.started_tool_call_ids
        and not context.runtime.completed_tool_call_ids
        and (summarized_names := _summarize_tool_call_names(streamed_tool_calls)) is not None
    ):
        return (
            "Tool calls are disabled for this request. "
            f"The model attempted to call: {summarized_names}."
        )
    return tool_call_terminal_message


def collect_chat_stream_success_snapshot(
    *,
    context: ChatStreamFinalizeContext,
    thinking_tail_duration_ms: int,
) -> ChatStreamSuccessSnapshot:
    final_payload_state = _collect_final_payload_state(context)
    pending_visible_text = _resolve_pending_visible_text(context=context)
    duration_ms = max(0, monotonic_ms() - context.runtime.started_at_monotonic_ms)
    has_visible_text = bool(
        context.runtime.assistant_visible_text.strip() or pending_visible_text.strip(),
    )
    has_visible_tool_calls = bool(context.stream_transcript.get_tool_calls()) or bool(
        context.runtime.emitted_tool_call_ids,
    )
    has_visible_thinking_phase = bool(context.thinking_phases)
    has_visible_images = context.runtime.assistant_images_emitted > 0
    return ChatStreamSuccessSnapshot(
        finish_reason=final_payload_state.finish_reason,
        usage=final_payload_state.usage,
        context_usage=final_payload_state.context_usage,
        pending_visible_text=pending_visible_text,
        duration_ms=duration_ms,
        thinking_tail_duration_ms=thinking_tail_duration_ms,
        has_visible_text=has_visible_text,
        has_visible_thinking_phase=has_visible_thinking_phase,
        has_visible_tool_calls=has_visible_tool_calls,
        has_visible_images=has_visible_images,
        tool_call_terminal_message=_resolve_terminal_tool_call_message(context),
    )

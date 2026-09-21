"""SoAI - Assistant timeline live status preview state helpers [backend/features/assistant_timeline/status_preview_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.content_text_rendering import render_openai_content_text
from core.serialization.json_parsing import parse_json_value
from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    StatusPreviewRequest,
    StatusPreviewToolSnapshot,
)
from features.assistant_timeline.status_preview_constants import (
    STATUS_PREVIEW_IDLE_CHECK_INTERVAL_MS,
    STATUS_PREVIEW_INITIAL_DELAY_MS,
    STATUS_PREVIEW_MAX_EXCERPT_CHARS,
    STATUS_PREVIEW_STALE_INTERVAL_MS,
    STATUS_PREVIEW_START_COOLDOWN_MS,
    STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
)
from features.assistant_timeline.status_preview_phase import (
    resolve_status_preview_phase,
)
from features.assistant_timeline.status_preview_state_keys import (
    resolve_status_preview_argument_detail_keys,
)
from features.assistant_timeline.status_preview_text_primitives import (
    collapse_status_preview_whitespace,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_status_preview_request",
    "clear_status_preview_state",
    "record_status_preview_tool_completion",
    "resolve_latest_user_message_excerpt",
    "resolve_status_preview_next_due_ms",
    "resolve_status_preview_tool_detail",
    "resolve_status_preview_trigger",
    "supersede_completed_tool_preview_with_running_thinking",
)


def resolve_latest_user_message_excerpt(request_json: JSONDict) -> str:
    messages_value = request_json.get("messages")
    if not isinstance(messages_value, list):
        return ""
    for item in reversed(messages_value):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        content_text = collapse_status_preview_whitespace(
            render_openai_content_text(item.get("content")),
            max_chars=STATUS_PREVIEW_MAX_EXCERPT_CHARS,
        )
        if content_text:
            return content_text
    return ""


def build_status_preview_request(
    *,
    runtime: AssistantTimelineRuntime,
) -> StatusPreviewRequest | None:
    latest_user_message_excerpt = collapse_status_preview_whitespace(
        runtime.latest_user_message_excerpt,
        max_chars=STATUS_PREVIEW_MAX_EXCERPT_CHARS,
    )
    if not latest_user_message_excerpt:
        return None
    visible_assistant_excerpt = collapse_status_preview_whitespace(
        runtime.assistant_visible_text,
        max_chars=STATUS_PREVIEW_MAX_EXCERPT_CHARS,
    )
    current_shown_label = collapse_status_preview_whitespace(
        runtime.status_preview_last_text or "",
        max_chars=STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
    )
    return StatusPreviewRequest(
        latest_user_message_excerpt=latest_user_message_excerpt,
        current_phase=resolve_status_preview_phase(runtime),
        latest_visible_assistant_text_excerpt=visible_assistant_excerpt,
        latest_completed_tool=runtime.status_preview_latest_completed_tool,
        current_shown_label=current_shown_label,
    )


def resolve_status_preview_next_due_ms(*, runtime: AssistantTimelineRuntime, now_ms: int) -> int:
    if not str(runtime.latest_user_message_excerpt or "").strip():
        return STATUS_PREVIEW_IDLE_CHECK_INTERVAL_MS
    turn_age_ms = max(0, now_ms - runtime.started_at_monotonic_ms)
    if turn_age_ms < STATUS_PREVIEW_INITIAL_DELAY_MS:
        return STATUS_PREVIEW_INITIAL_DELAY_MS - turn_age_ms
    request_cooldown_remaining_ms = max(
        0,
        (runtime.status_preview_last_started_monotonic_ms + STATUS_PREVIEW_START_COOLDOWN_MS)
        - now_ms,
    )
    if runtime.status_preview_pending_refresh:
        return request_cooldown_remaining_ms
    if runtime.status_preview_latest_completed_tool is not None:
        return STATUS_PREVIEW_IDLE_CHECK_INTERVAL_MS
    if not runtime.status_preview_real_emitted:
        return request_cooldown_remaining_ms
    stale_age_ms = max(0, now_ms - runtime.status_preview_last_completed_monotonic_ms)
    if stale_age_ms >= STATUS_PREVIEW_STALE_INTERVAL_MS:
        wait_ms = request_cooldown_remaining_ms
    else:
        wait_ms = max(
            request_cooldown_remaining_ms,
            STATUS_PREVIEW_STALE_INTERVAL_MS - stale_age_ms,
        )
    return wait_ms


def resolve_status_preview_trigger(*, runtime: AssistantTimelineRuntime, now_ms: int) -> str | None:
    if not str(runtime.latest_user_message_excerpt or "").strip():
        return None
    if max(0, now_ms - runtime.started_at_monotonic_ms) < STATUS_PREVIEW_INITIAL_DELAY_MS:
        return None
    if (
        runtime.status_preview_last_started_monotonic_ms > 0
        and now_ms - runtime.status_preview_last_started_monotonic_ms
        < STATUS_PREVIEW_START_COOLDOWN_MS
    ):
        return None
    if runtime.status_preview_pending_refresh:
        if runtime.status_preview_latest_completed_tool is not None:
            return "tool_call_completed"
        return "thinking_phase"
    if runtime.status_preview_latest_completed_tool is not None:
        return None
    if not runtime.status_preview_real_emitted:
        return "initial_interval"
    if (
        runtime.status_preview_last_completed_monotonic_ms > 0
        and now_ms - runtime.status_preview_last_completed_monotonic_ms
        >= STATUS_PREVIEW_STALE_INTERVAL_MS
    ):
        return "stale_interval"
    return None


def clear_status_preview_state(*, runtime: AssistantTimelineRuntime, now_ms: int) -> None:
    runtime.status_preview_generation += 1
    runtime.status_preview_last_text = None
    runtime.status_preview_last_key = None
    runtime.status_preview_last_args = None
    runtime.status_preview_last_generated_at_ms = 0
    runtime.status_preview_last_trigger = None
    runtime.status_preview_last_completed_monotonic_ms = max(0, now_ms)
    runtime.status_preview_real_emitted = True
    runtime.status_preview_pending_refresh = False
    runtime.status_preview_latest_completed_tool = None


def supersede_completed_tool_preview_with_running_thinking(
    *, runtime: AssistantTimelineRuntime, status: str
) -> bool:
    if status != "running":
        return False
    if runtime.status_preview_latest_completed_tool is None:
        return False
    runtime.status_preview_generation += 1
    runtime.status_preview_latest_completed_tool = None
    runtime.status_preview_pending_refresh = True
    return True


def record_status_preview_tool_completion(
    *,
    runtime: AssistantTimelineRuntime,
    tool_payload: JSONDict,
) -> bool:
    def is_primary_tool_name(value: str) -> bool:
        normalized = value.strip()
        if not normalized:
            return False
        if normalized == "subagent_spawn":
            return False
        return not normalized.startswith("subagent_")

    tool_name_value = tool_payload.get("tool_name")
    if not isinstance(tool_name_value, str):
        return False
    tool_name = tool_name_value.strip()
    if not tool_name:
        return False
    if not is_primary_tool_name(tool_name):
        return False

    runtime.status_preview_primary_completed_tool_calls += 1
    runtime.status_preview_generation += 1
    runtime.status_preview_latest_completed_tool = StatusPreviewToolSnapshot(
        tool_name=tool_name,
        detail=resolve_status_preview_tool_detail(tool_payload),
    )
    runtime.status_preview_pending_refresh = (
        runtime.status_preview_primary_completed_tool_calls >= 1
    )
    return runtime.status_preview_pending_refresh


def resolve_status_preview_tool_detail(tool_payload: JSONDict) -> str | None:
    tool_name = str(tool_payload.get("tool_name") or "").strip()
    arguments_value = tool_payload.get("arguments")
    if isinstance(arguments_value, dict):
        parsed_value: JSONValue | None = arguments_value
    elif isinstance(arguments_value, str):
        arguments_text = arguments_value.strip()
        if not arguments_text:
            return None
        parsed_value = _try_load_status_preview_arguments(arguments_text)
    else:
        return None
    if parsed_value is None:
        return None
    if isinstance(parsed_value, dict):
        for key in resolve_status_preview_argument_detail_keys(tool_name=tool_name):
            raw_value = parsed_value.get(key)
            resolved = _coerce_status_preview_tool_detail(raw_value)
            if resolved is not None:
                return resolved
    if isinstance(parsed_value, list):
        resolved = _coerce_status_preview_tool_detail(parsed_value)
        if resolved is not None:
            return resolved
    return None


def _try_load_status_preview_arguments(value: str) -> JSONValue | None:
    try:
        loaded = parse_json_value(value)
    except (ValidationError, ValueError):
        return None
    return loaded


def _coerce_status_preview_tool_detail(value: JSONValue) -> str | None:
    if isinstance(value, str):
        normalized = collapse_status_preview_whitespace(
            value,
            max_chars=STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
        )
        return normalized or None
    if isinstance(value, int | float | bool):
        normalized_number = collapse_status_preview_whitespace(
            str(value),
            max_chars=STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
        )
        return normalized_number or None
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            normalized_part: str | None = None
            if isinstance(item, str):
                normalized_part = collapse_status_preview_whitespace(
                    item,
                    max_chars=STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
                )
            elif isinstance(item, int | float | bool):
                normalized_part = collapse_status_preview_whitespace(
                    str(item),
                    max_chars=STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
                )
            if normalized_part:
                parts.append(normalized_part)
            if len(parts) >= 2:
                break
        if not parts:
            return None
        return collapse_status_preview_whitespace(
            ", ".join(parts),
            max_chars=STATUS_PREVIEW_TOOL_DETAIL_MAX_CHARS,
        )
    return None

"""SoAI - Assistant timeline terminal persistence [backend/features/assistant_timeline/assistant_timeline_terminal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.usage.serialization import (
    extract_public_usage_payload,
    is_aggregate_usage_source,
)
from core.tasks.enums import TaskStatus
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
)
from core.types.json_value import coerce_json_dict
from features.assistant_timeline.assistant_timeline_shutdown import (
    stop_timeline_session_tickers,
)
from features.assistant_timeline.assistant_timeline_terminal_support import (
    publish_assistant_timeline_message_events,
    wait_for_task_terminal_state,
)
from features.assistant_timeline.stream_finalize_cancelled import (
    finalize_chat_stream_cancelled,
)
from features.assistant_timeline.stream_finalize_context import (
    build_chat_stream_finalize_context,
)
from features.assistant_timeline.stream_finalize_error import finalize_chat_stream_error
from features.assistant_timeline.stream_finalize_success import (
    finalize_chat_stream_success,
)

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = (
    "finalize_agentic_stream_timeline",
    "finalize_assistant_timeline_agentic",
    "finalize_assistant_timeline_cancelled",
    "finalize_assistant_timeline_error",
    "finalize_assistant_timeline_non_agentic",
)


def _coerce_public_usage_payload_to_internal(
    usage_payload: JSONValue,
) -> JSONDict | None:
    public_usage = extract_public_usage_payload(usage_payload)
    if public_usage is None:
        return None
    return {
        "prompt_tokens": public_usage["prompt_tokens"],
        "completion_tokens": public_usage["completion_tokens"],
        "total_tokens": public_usage["total_tokens"],
        "usage_source": "provider_reported",
    }


def _is_aggregate_usage_payload(value: JSONDict) -> bool:
    return is_aggregate_usage_source(value.get("usage_source"))


async def finalize_assistant_timeline_non_agentic(
    session: AssistantTimelineSession,
    *,
    task: Task,
    task_lookup: Callable[[str], Awaitable[Task | None]],
) -> None:
    if session.runtime.cancellation_requested:
        await finalize_assistant_timeline_cancelled(
            session,
            session.runtime.cancellation_reason or "Chat stream was cancelled.",
        )
        return
    refreshed_task = await wait_for_task_terminal_state(
        task_id=task.task_id,
        task_lookup=task_lookup,
    )
    if refreshed_task is None:
        await finalize_assistant_timeline_error(
            session,
            message="Chat stream task state is unavailable.",
            code="server_error",
        )
        return
    if session.runtime.cancellation_requested:
        await finalize_assistant_timeline_cancelled(
            session,
            session.runtime.cancellation_reason
            or refreshed_task.error_message
            or refreshed_task.status_message
            or "Chat stream was cancelled.",
        )
        return
    if refreshed_task.status == TaskStatus.COMPLETED:
        result_payload = coerce_json_dict(refreshed_task.result)
        if result_payload is not None and session.runtime.canonical_usage is None:
            internal_usage = _coerce_public_usage_payload_to_internal(result_payload.get("usage"))
            if internal_usage is not None:
                session.runtime.canonical_usage = internal_usage
        finalized = await finalize_chat_stream_success(
            build_chat_stream_finalize_context(
                session.runtime,
                session.stream_transcript,
                session.thinking_phases,
                session.thinking_state,
                session.database_messages,
                session.database_tool_calls,
                session.task_registry,
                session.event_bus,
            ),
        )
        if finalized:
            await publish_assistant_timeline_message_events(session)
        return
    if refreshed_task.status == TaskStatus.CANCELLED:
        await finalize_assistant_timeline_cancelled(
            session,
            session.runtime.cancellation_reason
            or refreshed_task.error_message
            or refreshed_task.status_message
            or "Chat stream was cancelled.",
        )
        return
    if refreshed_task.status == TaskStatus.FAILED:
        await finalize_assistant_timeline_error(
            session,
            message=refreshed_task.error_message
            or refreshed_task.status_message
            or "Chat stream failed.",
            code=refreshed_task.error_type or "server_error",
        )
        return
    await finalize_assistant_timeline_error(
        session,
        message=refreshed_task.error_message
        or refreshed_task.status_message
        or "Chat stream failed.",
        code="server_error",
    )


async def finalize_assistant_timeline_agentic(
    session: AssistantTimelineSession,
    *,
    turn_state: JSONDict | None,
    resolve_terminal_outcome: Callable[[JSONDict | None], tuple[str, str | None, str | None]],
) -> None:
    terminal_outcome, terminal_message, terminal_code = resolve_terminal_outcome(turn_state)
    if isinstance(turn_state, dict):
        token_usage = coerce_json_dict(turn_state.get("token_usage"))
        if token_usage is not None:
            session.runtime.aggregate_usage = token_usage
            if session.runtime.canonical_usage is None and not _is_aggregate_usage_payload(
                token_usage
            ):
                session.runtime.canonical_usage = token_usage
    if terminal_outcome == TOOL_CALL_STATUS_COMPLETED:
        finalized = await finalize_chat_stream_success(
            build_chat_stream_finalize_context(
                session.runtime,
                session.stream_transcript,
                session.thinking_phases,
                session.thinking_state,
                session.database_messages,
                session.database_tool_calls,
                session.task_registry,
                session.event_bus,
            ),
            flush_pending_tool_events_before_terminal_synthesis=True,
        )
        if finalized:
            await publish_assistant_timeline_message_events(session)
        return
    if terminal_outcome == TOOL_CALL_STATUS_CANCELLED:
        await finalize_assistant_timeline_cancelled(
            session,
            terminal_message or "Chat stream was cancelled.",
            code=terminal_code or "cancelled",
        )
        return
    await finalize_assistant_timeline_error(
        session,
        message=terminal_message or "Chat stream failed.",
        code=terminal_code or "server_error",
    )


async def finalize_assistant_timeline_cancelled(
    session: AssistantTimelineSession,
    reason: str,
    *,
    code: str = "cancelled",
) -> None:
    finalized = await finalize_chat_stream_cancelled(
        build_chat_stream_finalize_context(
            session.runtime,
            session.stream_transcript,
            session.thinking_phases,
            session.thinking_state,
            session.database_messages,
            session.database_tool_calls,
            session.task_registry,
            session.event_bus,
        ),
        reason=reason,
        code=code,
    )
    if finalized:
        await publish_assistant_timeline_message_events(session)


async def finalize_assistant_timeline_error(
    session: AssistantTimelineSession,
    *,
    message: str,
    code: str,
) -> None:
    finalized = await finalize_chat_stream_error(
        build_chat_stream_finalize_context(
            session.runtime,
            session.stream_transcript,
            session.thinking_phases,
            session.thinking_state,
            session.database_messages,
            session.database_tool_calls,
            session.task_registry,
            session.event_bus,
        ),
        message=message,
        code=code,
        flush_deferred_visible_text=True,
    )
    if finalized:
        await publish_assistant_timeline_message_events(session)


async def finalize_agentic_stream_timeline(
    session: AssistantTimelineSession,
    *,
    turn_state_loader: Callable[[], Awaitable[JSONDict | None]],
    resolve_terminal_outcome: Callable[[JSONDict | None], tuple[str, str | None, str | None]],
) -> str:
    turn_state = await turn_state_loader()
    terminal_outcome, terminal_message, terminal_code = resolve_terminal_outcome(turn_state)
    await stop_timeline_session_tickers(session)
    await finalize_assistant_timeline_agentic(
        session,
        turn_state=turn_state,
        resolve_terminal_outcome=lambda _turn_state: (
            terminal_outcome,
            terminal_message,
            terminal_code,
        ),
    )
    return terminal_outcome

"""SoAI - Shared assistant timeline runtime models [backend/features/assistant_timeline/models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
)
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.conversations.conversation_input_finalization import (
        ConversationInputFinalization,
    )
    from core.openai.token_estimation_profile import TokenEstimationProfile

__all__ = (
    "AssistantTimelineRuntime",
    "PendingAssistantMessageEvent",
    "PendingToolEvent",
    "StatusPreviewRequest",
    "StatusPreviewResult",
    "StatusPreviewToolSnapshot",
    "TimelineActivity",
    "ToolCallLayout",
    "ToolCallPersistenceIdentity",
)


@dataclass(slots=True)
class PendingToolEvent:
    sequence_index: int
    thinking_index_before: int
    event_type: str
    tool_payload: JSONDict


@dataclass(slots=True)
class ToolCallLayout:
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None = None


@dataclass(slots=True)
class ToolCallPersistenceIdentity:
    message_index: int
    assistant_identity: AssistantTurnVariantIdentity
    turn_id: str | None = None
    iteration_index: int | None = None


@dataclass(slots=True)
class PendingAssistantMessageEvent:
    sequence: int
    assistant_revision: int
    event_type: str
    payload: JSONDict
    created_at: int


@dataclass(slots=True)
class TimelineActivity:
    status: str
    duration_ms: int = 0
    started_at_epoch_ms: int | None = None
    started_at_monotonic_ms: int | None = None


@dataclass(frozen=True, slots=True)
class StatusPreviewToolSnapshot:
    tool_name: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class StatusPreviewRequest:
    latest_user_message_excerpt: str
    current_phase: str
    latest_visible_assistant_text_excerpt: str
    latest_completed_tool: StatusPreviewToolSnapshot | None
    current_shown_label: str


@dataclass(frozen=True, slots=True)
class StatusPreviewResult:
    preview_key: str
    preview_args: JSONDict | None
    generated_at_ms: int


@dataclass(slots=True)
class AssistantTimelineRuntime:
    conv_id: str
    request_id: str
    assistant_at_ms: int
    assistant_turn_at_ms: int
    user_id: int
    message_index: int
    model_id: str | None
    model_variant_index: int
    started_at_epoch_ms: int
    started_at_monotonic_ms: int
    task_cancellation_id: str
    input_finalization: ConversationInputFinalization | None = None
    input_terminal_state: str | None = None
    input_terminal_code: str | None = None
    mutation_guard: Callable[[], Awaitable[None]] | None = None
    agent_turn_id: str | None = None
    agent_turn_execution_token: str | None = None
    agent_turn_cancellation_id: str | None = None
    agent_tool_events_authoritative: bool = False
    cancellation_requested: bool = False
    cancellation_reason: str | None = None
    last_visible_activity_monotonic_ms: int = 0
    loading_activity: TimelineActivity = field(
        default_factory=lambda: TimelineActivity(status="running"),
    )
    wait_for_user_activity: TimelineActivity = field(
        default_factory=lambda: TimelineActivity(status="idle"),
    )
    processing_activity: TimelineActivity = field(
        default_factory=lambda: TimelineActivity(status="idle"),
    )
    next_sequence: int = 0
    assistant_revision: int = 0
    assistant_visible_chunks: list[str] = field(default_factory=list[str])
    assistant_visible_chars: int = 0
    assistant_persisted_chars: int = 0
    assistant_last_persist_monotonic_ms: int = 0
    assistant_delta_buffer: list[str] = field(default_factory=list[str])
    assistant_delta_buffer_chars: int = 0
    assistant_delta_last_emit_ms: int = 0
    assistant_delta_emitted: bool = False
    assistant_images_emitted: int = 0
    emitted_image_urls: set[str] = field(default_factory=set[str])
    assistant_visible_output_started: bool = False
    assistant_event_buffer: list[PendingAssistantMessageEvent] = field(
        default_factory=list[PendingAssistantMessageEvent],
    )
    assistant_event_last_flush_monotonic_ms: int = 0
    latest_message_write_last_modified_at_ms: int | None = None
    latest_message_write_count: int | None = None
    thinking_phase_cursor: int = 0
    thinking_phases: list[JSONDict] | None = None
    pending_tool_events: list[PendingToolEvent] | None = None
    emitted_tool_call_ids: set[str] = field(default_factory=set[str])
    emitted_tool_call_started_ids: set[str] = field(default_factory=set[str])
    tool_name_by_call_id: dict[str, str] = field(default_factory=dict[str, str])
    latest_tool_payload_by_call_id: dict[str, JSONDict] = field(default_factory=dict[str, JSONDict])
    tool_call_started_at_ms_by_call_id: dict[str, int] = field(default_factory=dict[str, int])
    started_tool_call_ids: set[str] = field(default_factory=set[str])
    completed_tool_call_ids: set[str] = field(default_factory=set[str])
    running_tool_call_ids: set[str] = field(default_factory=set[str])
    pending_tool_output_deltas_by_call_id: dict[str, list[str]] = field(
        default_factory=dict[str, list[str]],
    )
    tool_output_by_call_id: dict[str, str] = field(default_factory=dict[str, str])
    tool_output_delta_last_flush_monotonic_ms_by_call_id: dict[str, int] = field(
        default_factory=dict[str, int],
    )
    tool_call_layout_by_call_id: dict[str, ToolCallLayout] = field(
        default_factory=dict[str, ToolCallLayout],
    )
    tool_call_sequence_index_by_call_id: dict[str, int] = field(default_factory=dict[str, int])
    tool_call_call_id_by_sequence_index: dict[int, str] = field(default_factory=dict[int, str])
    tool_call_identity_by_call_id: dict[str, ToolCallPersistenceIdentity] = field(
        default_factory=dict[str, ToolCallPersistenceIdentity],
    )
    active_task_id: str | None = None
    detach_event: asyncio.Event | None = None
    runner_task: asyncio.Task[None] | None = None
    publish_lock: asyncio.Lock | None = None
    publish_operation_lock: asyncio.Lock | None = None
    stream_state_force_flush_future: asyncio.Future[bool] | None = None
    terminal_finalization_started: bool = False
    terminal_event_emitted: bool = False
    terminal_event_published: bool = False
    terminal_persistence_attempted: bool = False
    terminal_persistence_completed: bool = False
    assistant_placeholder_persisted: bool = False
    quota_key_id: str | None = None
    quota_token_reservation: JSONDict | None = None
    quota_release_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    quota_prompt_tokens: int | None = None
    usage_preview_prompt_tokens: int = 0
    usage_preview_context_window_tokens: int | None = None
    usage_preview_context_window_unverified: bool = False
    usage_preview_prompt_tokens_capped: bool = False
    usage_preview_prompt_tokens_capped_reason: str | None = None
    usage_preview_prompt_precision: Literal["exact", "estimated"] = "exact"
    usage_preview_token_estimation_profile: TokenEstimationProfile | None = None
    usage_preview_completion_baseline_tokens: int = 0
    usage_preview_snapshot: JSONDict | None = None
    usage_preview_revision: int = 0
    usage_preview_last_compute_ms: int = 0
    usage_preview_last_emit_ms: int = 0
    usage_preview_last_completion_tokens: int | None = None
    usage_preview_estimated_completion_tokens: int = 0
    usage_preview_last_token_at_ms: int | None = None
    usage_preview_completion_rate_tokens_per_second: float = 0.0
    canonical_usage: JSONDict | None = None
    aggregate_usage: JSONDict | None = None
    post_terminal_tool_call_ids: set[str] = field(default_factory=set[str])
    latest_user_message_excerpt: str = ""
    status_preview_last_text: str | None = None
    status_preview_last_key: str | None = None
    status_preview_last_args: JSONDict | None = None
    status_preview_last_generated_at_ms: int = 0
    status_preview_last_trigger: str | None = None
    status_preview_last_completed_monotonic_ms: int = 0
    status_preview_last_started_monotonic_ms: int = 0
    status_preview_real_emitted: bool = False
    status_preview_pending_refresh: bool = False
    status_preview_latest_completed_tool: StatusPreviewToolSnapshot | None = None
    status_preview_primary_completed_tool_calls: int = 0
    status_preview_generation: int = 0
    status_preview_active_request_task: asyncio.Task[None] | None = None
    status_preview_wake_event: asyncio.Event | None = None

    def __post_init__(self) -> None:
        if self.last_visible_activity_monotonic_ms <= 0:
            self.last_visible_activity_monotonic_ms = self.started_at_monotonic_ms
        if self.assistant_last_persist_monotonic_ms <= 0:
            self.assistant_last_persist_monotonic_ms = self.started_at_monotonic_ms
        if self.assistant_delta_last_emit_ms <= 0:
            self.assistant_delta_last_emit_ms = self.started_at_monotonic_ms
        if self.assistant_event_last_flush_monotonic_ms <= 0:
            self.assistant_event_last_flush_monotonic_ms = self.started_at_monotonic_ms

    def clear_quota_reservation(self) -> None:
        self.quota_key_id = None
        self.quota_token_reservation = None
        self.quota_prompt_tokens = None

    async def require_mutation_allowed(self) -> None:
        if self.mutation_guard is not None:
            await self.mutation_guard()

    @property
    def assistant_visible_text(self) -> str:
        if not self.assistant_visible_chunks:
            return ""
        if len(self.assistant_visible_chunks) == 1:
            return self.assistant_visible_chunks[0]
        return "".join(self.assistant_visible_chunks)

    @assistant_visible_text.setter
    def assistant_visible_text(self, value: str) -> None:
        normalized_value = value or ""
        if normalized_value:
            self.assistant_visible_chunks = [normalized_value]
            self.assistant_visible_chars = len(normalized_value)
        else:
            self.assistant_visible_chunks = []
            self.assistant_visible_chars = 0
        self.assistant_persisted_chars = min(
            self.assistant_persisted_chars,
            self.assistant_visible_chars,
        )

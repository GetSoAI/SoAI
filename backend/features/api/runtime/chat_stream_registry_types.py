"""SoAI - Chat stream registry lifecycle records [backend/features/api/runtime/chat_stream_registry_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "ChatStreamCancellationIntent",
    "ChatStreamRegistrySnapshot",
    "ChatStreamReservation",
    "chat_stream_registry_slot_accepts_runtime",
    "execution_owns_runtime",
)


def execution_owns_runtime(
    execution_request_id: str,
    runtime: AssistantTimelineRuntime,
) -> bool:
    runtime_request_id = runtime.request_id
    if runtime_request_id == execution_request_id:
        return True
    variant_prefix = f"{execution_request_id}:variant:"
    variant_index = runtime_request_id.removeprefix(variant_prefix)
    return (
        runtime_request_id.startswith(variant_prefix)
        and bool(variant_index)
        and variant_index.isascii()
        and variant_index.isdigit()
    )


def chat_stream_registry_slot_accepts_runtime(
    existing: AssistantTimelineRuntime | None,
) -> bool:
    if existing is None:
        return True
    if existing.terminal_persistence_completed:
        return True
    return (
        existing.cancellation_requested
        and existing.detach_event is not None
        and existing.detach_event.is_set()
    )


@dataclass(frozen=True, slots=True)
class ChatStreamReservation:
    user_id: int
    conv_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class ChatStreamRegistrySnapshot:
    runtime: AssistantTimelineRuntime | None
    reservation: ChatStreamReservation | None
    cancellation_intent: ChatStreamCancellationIntent | None = None


@dataclass(frozen=True, slots=True)
class ChatStreamCancellationIntent:
    user_id: int
    conv_id: str
    request_id: str
    force_pending_steers: bool
    reason: str

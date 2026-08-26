"""SoAI - Chat stream runtime construction helpers [backend/features/assistant_timeline/runtime_construction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
)
from core.errors.exceptions import ValidationError
from core.timing.monotonic import monotonic_ms
from core.validation.strict_numbers import require_non_negative_int_strict
from core.validation.strings import require_trimmed_text
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable

    from core.types.json import JSONDict

__all__ = ("create_chat_stream_runtime",)


def create_chat_stream_runtime(
    *,
    conv_id: str,
    request_id: str,
    identity: AssistantTurnVariantIdentity,
    user_id: int,
    message_index: int,
    model_id: str | None,
    task_cancellation_id: str,
    started_at_epoch_ms: int | None = None,
    started_at_monotonic_ms: int | None = None,
    detach_event: asyncio.Event | None = None,
    quota_key_id: str | None = None,
    quota_token_reservation: JSONDict | None = None,
    quota_prompt_tokens: int | None = None,
    mutation_guard: Callable[[], Awaitable[None]] | None = None,
) -> AssistantTimelineRuntime:
    normalized_conv_id = require_trimmed_text(conv_id, "conv_id must be a non-empty string.")
    normalized_request_id = require_trimmed_text(
        request_id,
        "request_id must be a non-empty string.",
    )
    normalized_task_cancellation_id = require_trimmed_text(
        task_cancellation_id,
        "task_cancellation_id must be a non-empty string.",
    )
    normalized_user_id = int(user_id)
    if normalized_user_id < 1:
        raise ValidationError("user_id must be >= 1.")
    normalized_message_index = require_non_negative_int_strict(
        message_index,
        error_message="message_index must be a non-negative integer.",
    )
    normalized_model_variant_index = require_non_negative_int_strict(
        identity.model_variant_index,
        error_message="model_variant_index must be a non-negative integer.",
    )
    resolved_started_at_epoch_ms = (
        int(started_at_epoch_ms)
        if started_at_epoch_ms is not None and started_at_epoch_ms >= 0
        else int(identity.assistant_at_ms)
    )
    resolved_started_at_monotonic_ms = (
        int(started_at_monotonic_ms)
        if started_at_monotonic_ms is not None and started_at_monotonic_ms >= 0
        else int(monotonic_ms())
    )
    runtime = AssistantTimelineRuntime(
        conv_id=normalized_conv_id,
        request_id=normalized_request_id,
        assistant_at_ms=identity.assistant_at_ms,
        assistant_turn_at_ms=identity.assistant_turn_at_ms,
        user_id=normalized_user_id,
        message_index=normalized_message_index,
        model_id=model_id,
        model_variant_index=normalized_model_variant_index,
        started_at_epoch_ms=resolved_started_at_epoch_ms,
        started_at_monotonic_ms=resolved_started_at_monotonic_ms,
        task_cancellation_id=normalized_task_cancellation_id,
        mutation_guard=mutation_guard,
        detach_event=detach_event,
        quota_key_id=quota_key_id,
        quota_token_reservation=quota_token_reservation,
        quota_prompt_tokens=quota_prompt_tokens,
    )
    runtime.loading_activity.started_at_epoch_ms = int(runtime.assistant_at_ms)
    runtime.loading_activity.started_at_monotonic_ms = int(runtime.started_at_monotonic_ms)
    runtime.loading_activity.duration_ms = 0
    return runtime

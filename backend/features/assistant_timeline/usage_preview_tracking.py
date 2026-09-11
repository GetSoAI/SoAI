"""SoAI - Shared assistant timeline usage preview tracking [backend/features/assistant_timeline/usage_preview_tracking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import PromptOccupancy, build_token_usage_snapshot
from core.openai.token_rate_calculation import (
    TOKEN_RATE_UPDATE_INTERVAL_MS,
    calculate_smoothed_token_rate,
)
from core.timing.monotonic import monotonic_ms
from core.validation.integers import is_non_negative_strict_int

if TYPE_CHECKING:
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "finalize_runtime_usage_preview",
    "freeze_runtime_usage_preview",
    "take_usage_preview_snapshot_for_emit",
    "update_runtime_completion_usage_preview_if_due",
)


def _update_completion_rate(
    *,
    runtime: AssistantTimelineRuntime,
    token_delta: int,
    now_ms: int,
) -> None:
    if token_delta <= 0:
        return
    previous_token_at_ms = runtime.usage_preview_last_token_at_ms
    runtime.usage_preview_last_token_at_ms = now_ms
    if previous_token_at_ms is None or now_ms <= previous_token_at_ms:
        runtime.usage_preview_completion_rate_tokens_per_second = 0.0
        return
    runtime.usage_preview_completion_rate_tokens_per_second = calculate_smoothed_token_rate(
        previous_rate=runtime.usage_preview_completion_rate_tokens_per_second,
        token_delta=token_delta,
        elapsed_ms=now_ms - previous_token_at_ms,
    )


def update_runtime_completion_usage_preview_if_due(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    prompt_token_counter: PromptTokenCounter,
    now_ms: int | None = None,
) -> None:
    resolved_now_ms = monotonic_ms() if now_ms is None else int(now_ms)
    last_compute_ms = runtime.usage_preview_last_compute_ms
    if resolved_now_ms - last_compute_ms < TOKEN_RATE_UPDATE_INTERVAL_MS:
        return
    baseline_tokens = runtime.usage_preview_completion_baseline_tokens
    if not is_non_negative_strict_int(baseline_tokens):
        raise ValidationError(
            "Runtime usage preview completion baseline must be a non-negative integer.",
        )
    prompt_tokens = runtime.usage_preview_prompt_tokens
    if not is_non_negative_strict_int(prompt_tokens):
        raise ValidationError("Runtime usage preview prompt tokens must be a non-negative integer.")
    prompt_tokens_value = int(prompt_tokens)
    context_window = runtime.usage_preview_context_window_tokens
    if context_window is None:
        context_window_value = None
    else:
        if (
            isinstance(context_window, bool)
            or not isinstance(context_window, int)
            or context_window <= 0
        ):
            raise ValidationError(
                "Runtime usage preview context window must be a positive integer.",
            )
        context_window_value = int(context_window)
    fragments = stream_transcript.drain_completion_token_fragments()
    runtime.usage_preview_last_compute_ms = resolved_now_ms
    if not fragments:
        return
    model_name = runtime.model_id if runtime.model_id else None
    token_delta = prompt_token_counter.count_text_tokens(
        "".join(fragments),
        model_name=model_name,
        profile=runtime.usage_preview_token_estimation_profile,
    )
    completion_tokens = runtime.usage_preview_estimated_completion_tokens + token_delta
    runtime.usage_preview_estimated_completion_tokens = completion_tokens
    runtime.usage_preview_last_completion_tokens = completion_tokens
    _update_completion_rate(
        runtime=runtime,
        token_delta=token_delta,
        now_ms=resolved_now_ms,
    )
    context_completion_tokens = max(0, int(completion_tokens) - int(baseline_tokens))
    capped_reason_value = runtime.usage_preview_prompt_tokens_capped_reason
    occupancy = PromptOccupancy(
        prompt_tokens=prompt_tokens_value,
        capped=runtime.usage_preview_prompt_tokens_capped,
        capped_reason=(
            capped_reason_value.strip()
            if isinstance(capped_reason_value, str) and capped_reason_value.strip()
            else None
        ),
        precision=runtime.usage_preview_prompt_precision,
    )
    runtime.usage_preview_snapshot = build_token_usage_snapshot(
        occupancy=occupancy,
        usage_prompt_tokens=prompt_tokens_value,
        completion_tokens=int(completion_tokens),
        context_completion_tokens=context_completion_tokens,
        context_window_tokens=context_window_value,
        source="estimate",
        context_window_unverified=runtime.usage_preview_context_window_unverified,
    )
    runtime.usage_preview_revision += 1
    runtime.usage_preview_snapshot["preview_revision"] = runtime.usage_preview_revision
    runtime.usage_preview_snapshot["completion_rate_tokens_per_second"] = round(
        runtime.usage_preview_completion_rate_tokens_per_second,
        2,
    )


def finalize_runtime_usage_preview(
    *,
    runtime: AssistantTimelineRuntime,
    usage_prompt_tokens: int,
    completion_tokens: int,
    context_completion_tokens: int,
    usage_source: str,
) -> JSONDict:
    prompt_tokens = runtime.usage_preview_prompt_tokens
    if not is_non_negative_strict_int(prompt_tokens):
        raise ValidationError("Runtime usage preview prompt tokens must be a non-negative integer.")
    capped_reason_value = runtime.usage_preview_prompt_tokens_capped_reason
    occupancy = PromptOccupancy(
        prompt_tokens=int(prompt_tokens),
        capped=runtime.usage_preview_prompt_tokens_capped,
        capped_reason=(
            capped_reason_value.strip()
            if isinstance(capped_reason_value, str) and capped_reason_value.strip()
            else None
        ),
        precision=runtime.usage_preview_prompt_precision,
    )
    snapshot = build_token_usage_snapshot(
        occupancy=occupancy,
        usage_prompt_tokens=usage_prompt_tokens,
        completion_tokens=completion_tokens,
        context_completion_tokens=context_completion_tokens,
        context_window_tokens=runtime.usage_preview_context_window_tokens,
        source=usage_source,
        context_window_unverified=runtime.usage_preview_context_window_unverified,
    )
    runtime.usage_preview_revision += 1
    snapshot["preview_revision"] = runtime.usage_preview_revision
    snapshot["completion_rate_tokens_per_second"] = 0.0
    runtime.usage_preview_snapshot = snapshot
    runtime.usage_preview_completion_rate_tokens_per_second = 0.0
    runtime.usage_preview_last_completion_tokens = completion_tokens
    runtime.usage_preview_estimated_completion_tokens = completion_tokens
    runtime.usage_preview_last_token_at_ms = None
    return dict(snapshot)


def _require_snapshot_token(snapshot: JSONDict, key: str) -> int:
    value = snapshot.get(key)
    if not is_non_negative_strict_int(value):
        raise ValidationError(f"Runtime usage preview {key} must be a non-negative integer.")
    return int(value)


def freeze_runtime_usage_preview(
    *,
    runtime: AssistantTimelineRuntime,
) -> JSONDict | None:
    current_snapshot = runtime.usage_preview_snapshot
    if current_snapshot is None:
        runtime.usage_preview_completion_rate_tokens_per_second = 0.0
        runtime.usage_preview_last_token_at_ms = None
        return None
    usage_prompt_tokens = _require_snapshot_token(current_snapshot, "prompt_tokens")
    prompt_occupancy_tokens = _require_snapshot_token(
        current_snapshot,
        "prompt_occupancy_tokens",
    )
    completion_tokens = _require_snapshot_token(current_snapshot, "completion_tokens")
    context_completion_tokens = _require_snapshot_token(
        current_snapshot,
        "context_completion_tokens",
    )
    expected_total_tokens = _require_snapshot_token(current_snapshot, "total_tokens")
    expected_context_occupancy_tokens = _require_snapshot_token(
        current_snapshot,
        "context_occupancy_tokens",
    )
    snapshot_revision = _require_snapshot_token(current_snapshot, "preview_revision")
    if snapshot_revision != runtime.usage_preview_revision:
        raise ValidationError("Runtime usage preview revision is inconsistent.")
    context_window_value = current_snapshot.get("context_window_tokens")
    if context_window_value is not None and (
        isinstance(context_window_value, bool)
        or not isinstance(context_window_value, int)
        or context_window_value <= 0
    ):
        raise ValidationError("Runtime usage preview context window is invalid.")
    source_value = current_snapshot.get("source")
    if not isinstance(source_value, str) or not source_value.strip():
        raise ValidationError("Runtime usage preview source is invalid.")
    precision_value = current_snapshot.get("precision")
    if precision_value == "exact":
        precision: Literal["exact", "estimated"] = "exact"
    elif precision_value == "estimated":
        precision = "estimated"
    else:
        raise ValidationError("Runtime usage preview precision is invalid.")
    completion_rate_value = current_snapshot.get("completion_rate_tokens_per_second")
    if (
        isinstance(completion_rate_value, bool)
        or not isinstance(completion_rate_value, int | float)
        or not math.isfinite(float(completion_rate_value))
        or completion_rate_value < 0
    ):
        raise ValidationError("Runtime usage preview completion rate is invalid.")
    prompt_tokens_capped = current_snapshot.get("prompt_tokens_capped") is True
    capped_reason_value = current_snapshot.get("prompt_tokens_capped_reason")
    capped_reason = (
        capped_reason_value.strip()
        if isinstance(capped_reason_value, str) and capped_reason_value.strip()
        else None
    )
    occupancy = PromptOccupancy(
        prompt_tokens=prompt_occupancy_tokens,
        capped=prompt_tokens_capped,
        capped_reason=capped_reason,
        precision=precision,
    )
    budget_value = current_snapshot.get("budget_tokens")
    if budget_value is not None and not is_non_negative_strict_int(budget_value):
        raise ValidationError("Runtime usage preview budget tokens are invalid.")
    validated_snapshot = build_token_usage_snapshot(
        occupancy=occupancy,
        usage_prompt_tokens=usage_prompt_tokens,
        completion_tokens=completion_tokens,
        context_completion_tokens=context_completion_tokens,
        context_window_tokens=(
            int(context_window_value) if context_window_value is not None else None
        ),
        source=source_value,
        budget_tokens=(int(budget_value) if budget_value is not None else None),
        context_window_unverified=current_snapshot.get("context_window_unverified") is True,
    )
    if validated_snapshot["total_tokens"] != expected_total_tokens:
        raise ValidationError("Runtime usage preview total token count is inconsistent.")
    if validated_snapshot["context_occupancy_tokens"] != expected_context_occupancy_tokens:
        raise ValidationError("Runtime usage preview context occupancy is inconsistent.")
    current_fields = dict(current_snapshot)
    current_fields.pop("preview_revision", None)
    current_fields.pop("completion_rate_tokens_per_second", None)
    validated_fields = dict(validated_snapshot)
    validated_fields.pop("completion_rate_tokens_per_second", None)
    if current_fields != validated_fields:
        raise ValidationError("Runtime usage preview fields are inconsistent.")
    runtime.usage_preview_revision += 1
    snapshot = dict(current_snapshot)
    snapshot["preview_revision"] = runtime.usage_preview_revision
    snapshot["completion_rate_tokens_per_second"] = 0.0
    runtime.usage_preview_snapshot = snapshot
    runtime.usage_preview_last_completion_tokens = completion_tokens
    runtime.usage_preview_estimated_completion_tokens = completion_tokens
    runtime.usage_preview_completion_rate_tokens_per_second = 0.0
    runtime.usage_preview_last_token_at_ms = None
    return dict(snapshot)


def take_usage_preview_snapshot_for_emit(
    *,
    runtime: AssistantTimelineRuntime,
    now_ms: int | None = None,
    force: bool = False,
) -> JSONDict | None:
    snapshot = runtime.usage_preview_snapshot
    if snapshot is None:
        return None
    resolved_now_ms = monotonic_ms() if now_ms is None else int(now_ms)
    if (
        not force
        and resolved_now_ms - runtime.usage_preview_last_emit_ms < TOKEN_RATE_UPDATE_INTERVAL_MS
    ):
        return None
    runtime.usage_preview_last_emit_ms = resolved_now_ms
    return dict(snapshot)

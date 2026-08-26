"""SoAI - Central OpenAI token accounting primitives [backend/core/openai/token_accounting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.validation.integers import is_non_negative_strict_int, is_strict_int

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_counter_types import PromptTokenCountResult
    from core.openai.token_estimation_profile import TokenEstimationProfile

__all__ = (
    "PromptOccupancy",
    "build_prompt_occupancy_metadata",
    "build_prompt_occupancy_snapshot",
    "build_token_usage_snapshot",
    "count_history_prompt_occupancy",
    "count_prompt_occupancy",
    "count_prompt_occupancy_async",
    "resolve_explicit_prompt_occupancy",
)


@dataclass(frozen=True, slots=True)
class PromptOccupancy:
    prompt_tokens: int
    capped: bool
    capped_reason: str | None
    precision: Literal["exact", "estimated"]

    def __post_init__(self) -> None:
        if (
            isinstance(self.prompt_tokens, bool)
            or not isinstance(self.prompt_tokens, int)
            or self.prompt_tokens < 0
        ):
            raise ValidationError("Prompt tokens must be a non-negative integer.")
        if not isinstance(self.capped, bool):
            raise ValidationError("Prompt capped state must be a boolean.")
        if self.capped_reason is not None and (
            not isinstance(self.capped_reason, str) or not self.capped_reason.strip()
        ):
            raise ValidationError("Prompt capped reason must be a non-empty string.")
        if self.capped and self.capped_reason is None:
            raise ValidationError("Prompt capped reason is required for capped token counts.")
        if not self.capped and self.capped_reason is not None:
            raise ValidationError("Prompt capped reason requires a capped token count.")
        if self.precision not in ("exact", "estimated"):
            raise ValidationError("Prompt token precision is invalid.")


def _resolve_prompt_tokens(count_result: PromptTokenCountResult) -> int:
    if (
        isinstance(count_result.prompt_tokens, bool)
        or not isinstance(count_result.prompt_tokens, int)
        or count_result.prompt_tokens < 0
    ):
        raise ValidationError("Prompt token counter returned no token count.")
    return int(count_result.prompt_tokens)


def _resolve_capped(count_result: PromptTokenCountResult) -> bool:
    if not isinstance(count_result.capped, bool):
        raise ValidationError(
            "Prompt token counter returned invalid capped state.",
            details={"actual_type": type(count_result.capped).__name__},
        )
    return count_result.capped


def _require_prompt_token_count(prompt_tokens: int | None) -> int:
    if not is_non_negative_strict_int(prompt_tokens):
        raise ValidationError("Prompt token counter returned no token count.")
    return int(prompt_tokens)


def _resolve_context_window_tokens(context_window_tokens: int | None) -> int | None:
    if context_window_tokens is None:
        return None
    if not is_strict_int(context_window_tokens) or context_window_tokens <= 0:
        raise ValidationError("Context window tokens must be a positive integer.")
    return int(context_window_tokens)


def _resolve_budget_tokens(budget_tokens: int | None) -> int | None:
    if budget_tokens is None:
        return None
    if not is_non_negative_strict_int(budget_tokens):
        raise ValidationError("Budget tokens must be a non-negative integer.")
    return int(budget_tokens)


def _resolve_token_count(value: int, *, label: str) -> int:
    if isinstance(value, bool) or value < 0:
        raise ValidationError(f"{label} must be a non-negative integer.")
    return int(value)


def count_prompt_occupancy(
    *,
    prompt_token_counter: PromptTokenCounter,
    request_payload: JSONDict,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> PromptOccupancy:
    if token_estimation_profile is None:
        count_result = prompt_token_counter.count_prompt_tokens_with_result(request_payload)
    else:
        count_result = prompt_token_counter.count_prompt_tokens_with_result(
            request_payload,
            profile=token_estimation_profile,
        )
    capped_reason = (
        count_result.reason.strip()
        if isinstance(count_result.reason, str) and count_result.reason.strip()
        else None
    )
    capped = _resolve_capped(count_result)
    return PromptOccupancy(
        prompt_tokens=_resolve_prompt_tokens(count_result),
        capped=capped,
        capped_reason=capped_reason,
        precision="estimated" if capped or count_result.is_approximate else "exact",
    )


async def count_prompt_occupancy_async(
    *,
    prompt_token_counter: PromptTokenCounter,
    request_payload: JSONDict,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> PromptOccupancy:
    count_result = await prompt_token_counter.count_prompt_tokens_with_result_async(
        request_payload,
        profile=token_estimation_profile,
    )
    capped_reason = (
        count_result.reason.strip()
        if isinstance(count_result.reason, str) and count_result.reason.strip()
        else None
    )
    capped = _resolve_capped(count_result)
    return PromptOccupancy(
        prompt_tokens=_resolve_prompt_tokens(count_result),
        capped=capped,
        capped_reason=capped_reason,
        precision="estimated" if capped or count_result.is_approximate else "exact",
    )


def count_history_prompt_occupancy(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> PromptOccupancy:
    request_payload = dict(base_request_payload)
    request_payload["messages"] = list(message_history)
    return count_prompt_occupancy(
        prompt_token_counter=prompt_token_counter,
        request_payload=request_payload,
        token_estimation_profile=token_estimation_profile,
    )


def resolve_explicit_prompt_occupancy(
    prompt_tokens: int | None,
) -> PromptOccupancy | None:
    if prompt_tokens is None:
        return None
    return PromptOccupancy(
        prompt_tokens=_require_prompt_token_count(prompt_tokens),
        capped=False,
        capped_reason=None,
        precision="exact",
    )


def build_prompt_occupancy_snapshot(
    *,
    occupancy: PromptOccupancy,
    context_window_tokens: int | None,
    source: str,
    budget_tokens: int | None = None,
    context_window_unverified: bool = False,
) -> JSONDict:
    return build_token_usage_snapshot(
        occupancy=occupancy,
        usage_prompt_tokens=occupancy.prompt_tokens,
        completion_tokens=0,
        context_completion_tokens=0,
        context_window_tokens=context_window_tokens,
        source=source,
        budget_tokens=budget_tokens,
        context_window_unverified=context_window_unverified,
    )


def build_token_usage_snapshot(
    *,
    occupancy: PromptOccupancy,
    usage_prompt_tokens: int,
    completion_tokens: int,
    context_completion_tokens: int,
    context_window_tokens: int | None,
    source: str,
    budget_tokens: int | None = None,
    context_window_unverified: bool = False,
) -> JSONDict:
    resolved_usage_prompt_tokens = _resolve_token_count(
        usage_prompt_tokens,
        label="Usage prompt token count",
    )
    resolved_completion_tokens = _resolve_token_count(
        completion_tokens,
        label="Completion token count",
    )
    resolved_context_completion_tokens = _resolve_token_count(
        context_completion_tokens,
        label="Context completion token count",
    )
    if resolved_context_completion_tokens > resolved_completion_tokens:
        raise ValidationError(
            "Context completion token count cannot exceed completion token count.",
        )
    if not source.strip():
        raise ValidationError("Token usage source must be a non-empty string.")
    resolved_context_window_tokens = _resolve_context_window_tokens(context_window_tokens)
    resolved_budget_tokens = _resolve_budget_tokens(budget_tokens)
    context_occupancy_tokens = int(occupancy.prompt_tokens) + resolved_context_completion_tokens
    usage_preview: JSONDict = {
        "prompt_tokens": resolved_usage_prompt_tokens,
        "prompt_occupancy_tokens": int(occupancy.prompt_tokens),
        "completion_tokens": resolved_completion_tokens,
        "context_completion_tokens": resolved_context_completion_tokens,
        "context_occupancy_tokens": context_occupancy_tokens,
        "total_tokens": resolved_usage_prompt_tokens + resolved_completion_tokens,
        "context_window_tokens": resolved_context_window_tokens,
        "completion_rate_tokens_per_second": 0.0,
        "source": source.strip(),
        "precision": occupancy.precision,
    }
    if context_window_unverified:
        usage_preview["context_window_unverified"] = True
    if resolved_budget_tokens is not None:
        usage_preview["budget_tokens"] = resolved_budget_tokens
    if occupancy.capped:
        usage_preview["prompt_tokens_capped"] = True
        if occupancy.capped_reason is not None:
            usage_preview["prompt_tokens_capped_reason"] = occupancy.capped_reason
    return usage_preview


def build_prompt_occupancy_metadata(occupancy: PromptOccupancy) -> JSONDict:
    metadata: JSONDict = {
        "prompt_tokens": int(occupancy.prompt_tokens),
        "prompt_tokens_precision": occupancy.precision,
    }
    if occupancy.capped:
        metadata["prompt_tokens_capped"] = True
        if occupancy.capped_reason is not None:
            metadata["prompt_tokens_capped_reason"] = occupancy.capped_reason
    return metadata

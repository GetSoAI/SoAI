"""SoAI - Subagent token usage normalization [backend/features/agent/subagents/token_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import PromptOccupancy, build_token_usage_snapshot
from core.openai.usage.serialization import build_internal_usage_payload
from core.types.json import JSONDict, JSONValue

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.openai.usage.models import CanonicalUsage

__all__ = (
    "SubagentPromptTokenMetadata",
    "build_actual_subagent_token_usage",
    "build_estimated_subagent_token_usage",
    "read_subagent_prompt_token_metadata",
)


@dataclass(frozen=True, slots=True)
class SubagentPromptTokenMetadata:
    prompt_tokens: int
    capped: bool
    capped_reason: str | None
    precision: Literal["exact", "estimated"]

    def __post_init__(self) -> None:
        PromptOccupancy(
            prompt_tokens=self.prompt_tokens,
            capped=self.capped,
            capped_reason=self.capped_reason,
            precision=self.precision,
        )


def read_subagent_prompt_token_metadata(
    metadata: Mapping[str, JSONValue] | None,
) -> SubagentPromptTokenMetadata:
    if not isinstance(metadata, Mapping):
        raise ValidationError("Subagent prompt token metadata is unavailable.")
    prompt_tokens_value = metadata.get("prompt_tokens")
    if (
        isinstance(prompt_tokens_value, bool)
        or not isinstance(prompt_tokens_value, int)
        or prompt_tokens_value < 0
    ):
        raise ValidationError("Subagent prompt token metadata prompt_tokens is invalid.")
    prompt_tokens = int(prompt_tokens_value)
    capped_value = metadata.get("prompt_tokens_capped")
    if capped_value is not None and not isinstance(capped_value, bool):
        raise ValidationError("Subagent prompt token metadata capped state is invalid.")
    capped_reason_value = metadata.get("prompt_tokens_capped_reason")
    capped_reason = (
        capped_reason_value.strip()
        if isinstance(capped_reason_value, str) and capped_reason_value.strip()
        else None
    )
    precision_value = metadata.get("prompt_tokens_precision")
    if not isinstance(precision_value, str):
        raise ValidationError("Subagent prompt token metadata precision is invalid.")
    if precision_value == "exact":
        precision: Literal["exact", "estimated"] = "exact"
    elif precision_value == "estimated":
        precision = "estimated"
    else:
        raise ValidationError("Subagent prompt token metadata precision is invalid.")
    return SubagentPromptTokenMetadata(
        prompt_tokens=prompt_tokens,
        capped=capped_value is True,
        capped_reason=capped_reason,
        precision=precision,
    )


def build_estimated_subagent_token_usage(
    *,
    prompt_token_counter: PromptTokenCounter,
    requested_model: str,
    prompt_tokens: int,
    prompt_tokens_capped: bool,
    prompt_tokens_capped_reason: str | None,
    prompt_tokens_precision: Literal["exact", "estimated"],
    visible_text: str,
    token_estimation_profile: TokenEstimationProfile,
) -> JSONDict:
    completion_tokens = prompt_token_counter.count_text_tokens(
        visible_text,
        model_name=requested_model,
        profile=token_estimation_profile,
    )
    token_usage = build_token_usage_snapshot(
        occupancy=PromptOccupancy(
            prompt_tokens=prompt_tokens,
            capped=prompt_tokens_capped,
            capped_reason=prompt_tokens_capped_reason,
            precision=prompt_tokens_precision,
        ),
        usage_prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        context_completion_tokens=completion_tokens,
        context_window_tokens=None,
        source="estimate",
    )
    return token_usage


def build_actual_subagent_token_usage(
    *,
    usage: CanonicalUsage | None,
    prompt_tokens_capped: bool,
    prompt_tokens_capped_reason: str | None,
    prompt_tokens_precision: Literal["exact", "estimated"],
) -> JSONDict | None:
    if usage is None:
        return None
    if (
        int(usage.prompt_tokens) <= 0
        and int(usage.completion_tokens) <= 0
        and int(usage.total_tokens) <= 0
    ):
        return None
    occupancy = PromptOccupancy(
        prompt_tokens=int(usage.prompt_tokens),
        capped=prompt_tokens_capped,
        capped_reason=prompt_tokens_capped_reason,
        precision=prompt_tokens_precision,
    )
    token_usage = build_internal_usage_payload(usage)
    token_usage["prompt_occupancy_tokens"] = int(usage.prompt_tokens)
    token_usage["context_completion_tokens"] = int(usage.completion_tokens)
    token_usage["context_occupancy_tokens"] = int(usage.prompt_tokens) + int(
        usage.completion_tokens,
    )
    token_usage["source"] = "actual"
    token_usage["precision"] = occupancy.precision
    if occupancy.capped:
        token_usage["prompt_tokens_capped"] = True
        if occupancy.capped_reason is not None:
            token_usage["prompt_tokens_capped_reason"] = occupancy.capped_reason
    return token_usage

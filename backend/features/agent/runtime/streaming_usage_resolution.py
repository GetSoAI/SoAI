"""SoAI - Agent streaming usage resolution [backend/features/agent/runtime/streaming_usage_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.openai.token_accounting import count_prompt_occupancy_async
from core.openai.usage.resolution import resolve_canonical_usage
from features.agent.runtime.openai_payload import (
    coerce_usage_dict,
    resolve_payload_model,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.openai.usage.models import CanonicalUsage
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentStreamingInferenceOutcome

__all__ = ("resolve_streaming_step_usage",)

LOGGER_NAME = "SoAI.features.agent.streaming_usage_resolution"


async def resolve_streaming_step_usage(
    *,
    prompt_token_counter: PromptTokenCounter,
    request_payload: JSONDict,
    outcome: AgentStreamingInferenceOutcome,
    token_estimation_profile: TokenEstimationProfile,
) -> CanonicalUsage | None:
    if outcome.transcript is None:
        return coerce_usage_dict(outcome.usage)
    prompt_occupancy = await count_prompt_occupancy_async(
        prompt_token_counter=prompt_token_counter,
        request_payload=request_payload,
        token_estimation_profile=token_estimation_profile,
    )
    resolution = resolve_canonical_usage(
        transcript=outcome.transcript,
        explicit_usage_payload=outcome.usage,
        prompt_tokens_hint=prompt_occupancy.prompt_tokens,
        prompt_token_counter=prompt_token_counter,
        model_name=resolve_payload_model(request_payload),
        token_estimation_profile=token_estimation_profile,
    )
    if resolution.status not in {"accepted", "absent"}:
        get_logger(LOGGER_NAME).warning(
            "Rejected provider usage; reconstructed agent step usage from transcript (%s).",
            resolution.status,
        )
    return resolution.usage

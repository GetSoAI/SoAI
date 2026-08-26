"""SoAI - Chat stream runtime usage preview refresh [backend/features/api/runtime/chat_stream_usage_preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.token_accounting import (
    PromptOccupancy,
    build_prompt_occupancy_snapshot,
)
from core.openai.usage.transcript_completion_token_estimation import (
    estimate_transcript_completion_tokens,
)
from features.openai.model_aware_prompt_tokens import count_model_aware_prompt_occupancy

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelParameterServiceProtocol,
        ModelProviderCoordinatorProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.plugins.protocols import PluginManagerProtocol
    from core.runtime.request_context import RequestContext
    from core.state.protocols import StateAggregatorProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "refresh_chat_stream_usage_preview_from_inference_payload",
    "refresh_chat_stream_usage_preview_from_prompt_occupancy",
)


def _resolve_runtime_model_name(runtime: AssistantTimelineRuntime) -> str | None:
    return runtime.model_id if runtime.model_id else None


def _estimate_completion_baseline(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript | None,
    prompt_token_counter: PromptTokenCounter,
    token_estimation_profile: TokenEstimationProfile | None,
) -> int:
    if stream_transcript is None:
        return 0
    completion_tokens = estimate_transcript_completion_tokens(
        transcript=stream_transcript,
        prompt_token_counter=prompt_token_counter,
        model_name=_resolve_runtime_model_name(runtime),
        token_estimation_profile=token_estimation_profile,
    )
    stream_transcript.drain_completion_token_fragments()
    return completion_tokens


def _apply_prompt_usage_preview_snapshot(
    *,
    runtime: AssistantTimelineRuntime,
    occupancy: PromptOccupancy,
    context_window_tokens: int | None,
    context_window_unverified: bool,
    token_estimation_profile: TokenEstimationProfile | None,
    stream_transcript: OpenAIStreamTranscript | None,
    prompt_token_counter: PromptTokenCounter,
) -> None:
    runtime.usage_preview_prompt_tokens = occupancy.prompt_tokens
    runtime.usage_preview_context_window_tokens = context_window_tokens
    runtime.usage_preview_context_window_unverified = context_window_unverified
    runtime.usage_preview_prompt_tokens_capped = occupancy.capped
    runtime.usage_preview_prompt_tokens_capped_reason = occupancy.capped_reason
    runtime.usage_preview_prompt_precision = occupancy.precision
    runtime.usage_preview_token_estimation_profile = token_estimation_profile
    completion_baseline = _estimate_completion_baseline(
        runtime=runtime,
        stream_transcript=stream_transcript,
        prompt_token_counter=prompt_token_counter,
        token_estimation_profile=token_estimation_profile,
    )
    runtime.usage_preview_completion_baseline_tokens = completion_baseline
    runtime.usage_preview_estimated_completion_tokens = completion_baseline
    runtime.usage_preview_snapshot = build_prompt_occupancy_snapshot(
        occupancy=occupancy,
        context_window_tokens=context_window_tokens,
        source="prompt",
        context_window_unverified=context_window_unverified,
    )
    runtime.usage_preview_revision += 1
    runtime.usage_preview_snapshot["preview_revision"] = runtime.usage_preview_revision
    runtime.usage_preview_last_emit_ms = 0
    runtime.usage_preview_last_compute_ms = 0
    runtime.usage_preview_last_completion_tokens = None
    runtime.usage_preview_last_token_at_ms = None
    runtime.usage_preview_completion_rate_tokens_per_second = 0.0


async def refresh_chat_stream_usage_preview_from_inference_payload(
    *,
    runtime: AssistantTimelineRuntime,
    inference_request_payload: JSONDict,
    config: ConfigProtocol,
    prompt_token_counter: PromptTokenCounter,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_provider_coordinator: ModelProviderCoordinatorProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
    model_parameter_service: ModelParameterServiceProtocol,
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    orchestrator_lifecycle: OrchestratorLifecycleProtocol,
    request_context: RequestContext,
    stream_transcript: OpenAIStreamTranscript | None = None,
) -> None:
    occupancy, runtime_profile = await count_model_aware_prompt_occupancy(
        config=config,
        prompt_token_counter=prompt_token_counter,
        request_payload=inference_request_payload,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        model_parameter_service=model_parameter_service,
        provider_get_external=model_provider_coordinator.provider_get_external,
        plugin_manager=plugin_manager,
        virtual_model_get=virtual_model_get,
        state_aggregator=state_aggregator,
        orchestrator_lifecycle=orchestrator_lifecycle,
        request_context=request_context,
    )
    _apply_prompt_usage_preview_snapshot(
        runtime=runtime,
        occupancy=occupancy,
        context_window_tokens=runtime_profile.context_window_tokens,
        context_window_unverified=runtime_profile.context_window_unverified,
        token_estimation_profile=runtime_profile.token_estimation_profile,
        stream_transcript=stream_transcript,
        prompt_token_counter=prompt_token_counter,
    )


def refresh_chat_stream_usage_preview_from_prompt_occupancy(
    *,
    runtime: AssistantTimelineRuntime,
    occupancy: PromptOccupancy,
    stream_transcript: OpenAIStreamTranscript,
    prompt_token_counter: PromptTokenCounter,
) -> None:
    _apply_prompt_usage_preview_snapshot(
        runtime=runtime,
        occupancy=occupancy,
        context_window_tokens=runtime.usage_preview_context_window_tokens,
        context_window_unverified=runtime.usage_preview_context_window_unverified,
        token_estimation_profile=runtime.usage_preview_token_estimation_profile,
        stream_transcript=stream_transcript,
        prompt_token_counter=prompt_token_counter,
    )

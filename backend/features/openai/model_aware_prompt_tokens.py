"""SoAI - Model-aware OpenAI prompt token counting [backend/features/openai/model_aware_prompt_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.models.context_window import MODEL_PARAM_STANDARDIZED_NAME, coerce_positive_context_tokens
from core.models.reference_resolution import resolve_model_reference
from core.openai.request_fields import resolve_optional_model_name
from core.openai.token_accounting import PromptOccupancy, count_prompt_occupancy_async
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.types.json_value import copy_json_dict
from features.openai.model_prompt_token_targets import (
    ModelPromptCountTarget,
    build_model_prompt_count_targets,
    count_target_plugin_prompt_occupancy,
)
from features.openai.model_runtime_profile_resolution import (
    OpenAIModelRuntimeProfile,
    resolve_openai_model_runtime_profile,
)
from features.openai.prompt_token_aggregation import aggregate_prompt_occupancies
from features.openai.token_estimation_resolution import resolve_token_estimation_profile

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelParameterServiceProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.plugins.protocols import PluginManagerProtocol
    from core.runtime.request_context import RequestContext
    from core.state.protocols import StateAggregatorProtocol
    from core.types.json import JSONDict

__all__ = ("count_model_aware_prompt_occupancy",)


async def count_model_aware_prompt_occupancy(
    *,
    config: ConfigProtocol,
    prompt_token_counter: PromptTokenCounter,
    request_payload: JSONDict,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_parameter_service: ModelParameterServiceProtocol,
    provider_get_external: Callable[[str, bool], Awaitable[ExternalProviderInternalRecord | None]],
    plugin_manager: PluginManagerProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
    state_aggregator: StateAggregatorProtocol,
    orchestrator_lifecycle: OrchestratorLifecycleProtocol,
    request_context: RequestContext,
) -> tuple[PromptOccupancy, OpenAIModelRuntimeProfile]:
    model_name = resolve_optional_model_name(request_payload) or ""
    resolved_profile = await resolve_openai_model_runtime_profile(
        config=config,
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        provider_get_external=provider_get_external,
        virtual_model_get=virtual_model_get,
    )
    runtime_profile = _apply_payload_context_window_override(
        runtime_profile=resolved_profile,
        request_payload=request_payload,
    )
    fallback = await count_prompt_occupancy_async(
        prompt_token_counter=prompt_token_counter,
        request_payload=request_payload,
        token_estimation_profile=runtime_profile.token_estimation_profile,
    )
    reference = runtime_profile.reference
    if reference is None:
        return (fallback, runtime_profile)
    targets = build_model_prompt_count_targets(
        reference.universal_ids,
        runtime_profile.model_records,
    )
    if not targets:
        return (fallback, runtime_profile)
    target_fallbacks = await _count_target_fallbacks(
        targets=targets,
        prompt_token_counter=prompt_token_counter,
        request_payload=request_payload,
        initial_profile=runtime_profile.token_estimation_profile,
        initial_occupancy=fallback,
    )
    fallback_aggregate = aggregate_prompt_occupancies(
        target_fallbacks,
        max_counted_tokens=prompt_token_counter.max_counted_tokens,
    )
    if any(
        occupancy.capped and occupancy.capped_reason != "token_limit"
        for occupancy in target_fallbacks
    ):
        return (fallback_aggregate, runtime_profile)
    plugin_payload = await prompt_token_counter.run_blocking(copy_json_dict, request_payload)
    initial_reference = reference
    resolved_occupancies = list(target_fallbacks)
    try:
        async with asyncio.timeout(LONG_REQUEST_TIMEOUT_SEC):
            for index, target in enumerate(targets):
                exact = await count_target_plugin_prompt_occupancy(
                    target=target,
                    plugin_payload=plugin_payload,
                    request_payload=request_payload,
                    model_information_service=model_information_service,
                    model_parameter_service=model_parameter_service,
                    plugin_manager=plugin_manager,
                    state_aggregator=state_aggregator,
                    orchestrator_lifecycle=orchestrator_lifecycle,
                    request_context=request_context,
                )
                if exact is not None:
                    resolved_occupancies[index] = exact
    except TimeoutError:
        return (fallback_aggregate, runtime_profile)
    final_reference = await resolve_model_reference(
        model_name=model_name,
        model_resolution_service=model_resolution_service,
        virtual_model_get=virtual_model_get,
    )
    if final_reference != initial_reference:
        return (fallback_aggregate, runtime_profile)
    return (
        aggregate_prompt_occupancies(
            resolved_occupancies,
            max_counted_tokens=prompt_token_counter.max_counted_tokens,
        ),
        runtime_profile,
    )


async def _count_target_fallbacks(
    *,
    targets: tuple[ModelPromptCountTarget, ...],
    prompt_token_counter: PromptTokenCounter,
    request_payload: JSONDict,
    initial_profile: TokenEstimationProfile,
    initial_occupancy: PromptOccupancy,
) -> list[PromptOccupancy]:
    occupancies: list[PromptOccupancy] = []
    profile_occupancies = {initial_profile: initial_occupancy}
    for target in targets:
        profile = resolve_token_estimation_profile(
            model_name=str(target.model_info.get("source_model_id") or ""),
            provider_record=None,
            model_records=(target.model_info,),
        )
        occupancy = profile_occupancies.get(profile)
        if occupancy is None:
            occupancy = await count_prompt_occupancy_async(
                prompt_token_counter=prompt_token_counter,
                request_payload=request_payload,
                token_estimation_profile=profile,
            )
            profile_occupancies[profile] = occupancy
        occupancies.append(occupancy)
    return occupancies


def _apply_payload_context_window_override(
    *,
    runtime_profile: OpenAIModelRuntimeProfile,
    request_payload: JSONDict,
) -> OpenAIModelRuntimeProfile:
    override = coerce_positive_context_tokens(request_payload.get(MODEL_PARAM_STANDARDIZED_NAME))
    if override is None:
        return runtime_profile
    return OpenAIModelRuntimeProfile(
        context_window_tokens=override,
        context_window_unverified=False,
        token_estimation_profile=runtime_profile.token_estimation_profile,
        reference=runtime_profile.reference,
        model_records=runtime_profile.model_records,
    )

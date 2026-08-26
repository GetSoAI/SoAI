"""SoAI - Chat stream usage preview refresh callback [backend/features/api/runtime/chat_stream_usage_preview_callback.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from features.api.runtime.chat_stream_usage_preview import (
    refresh_chat_stream_usage_preview_from_inference_payload,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.logging.protocols import LoggerProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelParameterServiceProtocol,
        ModelProviderCoordinatorProtocol,
        ModelResolutionServiceProtocol,
    )
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.protocols_lifecycle import OrchestratorLifecycleProtocol
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.plugins.protocols import PluginManagerProtocol
    from core.runtime.request_context import RequestContext
    from core.state.protocols import StateAggregatorProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("build_chat_stream_usage_preview_refresh_callback",)

OPERATION_CHAT_STREAM_USAGE_PREVIEW_REFRESH = "chat_stream.usage_preview_refresh"


def build_chat_stream_usage_preview_refresh_callback(
    *,
    runtime: AssistantTimelineRuntime,
    logger: LoggerProtocol,
    trace_id: str,
    turn_id: str | None,
    config: ConfigProtocol,
    prompt_token_counter: PromptTokenCounter,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_provider_coordinator: ModelProviderCoordinatorProtocol,
    virtual_model_get: (
        Callable[[str], Awaitable[VirtualModelConfig | None] | VirtualModelConfig | None] | None
    ),
    stream_transcript: OpenAIStreamTranscript,
    model_parameter_service: ModelParameterServiceProtocol,
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    orchestrator_lifecycle: OrchestratorLifecycleProtocol,
    request_context: RequestContext,
) -> Callable[[JSONDict], Awaitable[None]]:
    async def refresh_usage_preview(payload: JSONDict) -> None:
        try:
            await refresh_chat_stream_usage_preview_from_inference_payload(
                runtime=runtime,
                inference_request_payload=payload,
                config=config,
                prompt_token_counter=prompt_token_counter,
                model_resolution_service=model_resolution_service,
                model_information_service=model_information_service,
                model_provider_coordinator=model_provider_coordinator,
                virtual_model_get=virtual_model_get,
                model_parameter_service=model_parameter_service,
                plugin_manager=plugin_manager,
                state_aggregator=state_aggregator,
                orchestrator_lifecycle=orchestrator_lifecycle,
                request_context=request_context,
                stream_transcript=stream_transcript,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_CHAT_STREAM_USAGE_PREVIEW_REFRESH,
            )
            log_handled_exception(
                logger,
                coerced,
                message="Failed to refresh chat stream usage preview (non-critical).",
                trace_id=trace_id,
                operation=OPERATION_CHAT_STREAM_USAGE_PREVIEW_REFRESH,
                level="debug",
                details={
                    "conv_id": runtime.conv_id,
                    "request_id": runtime.request_id,
                    "turn_id": turn_id,
                },
            )

    return refresh_usage_preview

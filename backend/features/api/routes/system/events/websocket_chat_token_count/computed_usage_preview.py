"""SoAI - WebSocket chat token computed usage preview [backend/features/api/routes/system/events/websocket_chat_token_count/computed_usage_preview.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.websocket_chat_token_count.payloads import (
    enqueue_token_count_profile_result,
    token_count_result_delivery,
)
from features.api.runtime.context import require_request_context_instance
from features.openai.model_aware_prompt_tokens import (
    count_model_aware_prompt_occupancy,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("enqueue_counted_usage_preview",)


async def enqueue_counted_usage_preview(
    *,
    api_context: ApiContext,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    conv_id: str,
    request_id: str,
    inference_request_json: JSONDict,
) -> None:
    provider_coordinator = api_context.dependencies.model_provider_coordinator
    occupancy, runtime_profile = await count_model_aware_prompt_occupancy(
        config=api_context.dependencies.config,
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        request_payload=inference_request_json,
        model_resolution_service=api_context.dependencies.model_resolution_service,
        model_information_service=api_context.dependencies.model_information_service,
        model_parameter_service=api_context.dependencies.model_parameter_service,
        provider_get_external=provider_coordinator.provider_get_external,
        plugin_manager=api_context.dependencies.plugin_manager,
        virtual_model_get=api_context.dependencies.model_virtual_model_service.virtual_model_get,
        state_aggregator=api_context.dependencies.state_aggregator,
        orchestrator_lifecycle=api_context.dependencies.orchestrator_lifecycle,
        request_context=require_request_context_instance(connection.request),
    )
    delivery = token_count_result_delivery(connection, enqueue_warning_tracker, conv_id, request_id)
    enqueue_token_count_profile_result(
        delivery,
        occupancy,
        runtime_profile,
        "prompt",
    )

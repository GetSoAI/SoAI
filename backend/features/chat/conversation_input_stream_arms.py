"""SoAI - Durable Chat input inference stream arms [backend/features/chat/conversation_input_stream_arms.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.request_field_filtering import build_inference_request_payload
from core.runtime.request_sources import REQUEST_SOURCE_WEBUI_WS
from core.tasks.type_catalog import TASK_TYPE_CHAT_COMPLETION
from features.agent.runtime.execution_preparation import build_agent_turn_engine_dependencies
from features.agent.runtime.streaming_inference_admission import (
    create_streaming_inference_task,
)
from features.agent.runtime.turn_iteration_policy_types import AgentOutputPublicationMode
from features.api.runtime.chat_execution.preview_contract import (
    build_preview_contract_validation_callback,
)
from features.api.runtime.chat_execution.task_metadata import (
    build_ws_chat_stream_task_metadata,
)
from features.api.runtime.chat_prompt_augmentation import request_requires_preview_contract
from features.api.runtime.chat_stream_usage_preview import (
    refresh_chat_stream_usage_preview_from_inference_payload,
)
from features.api.runtime.knowledge_prompt_delivery import (
    commit_knowledge_prompt_claim_noncritical,
)
from features.api.streaming.assistant_timeline.non_agent.stream_execution import (
    execute_timeline_non_agent_stream,
)
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.chat.conversation_agent_stream import execute_conversation_agent_stream

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )
    from features.assistant_timeline.models import AssistantTimelineRuntime
    from features.chat.conversation_input_turn_preparation import (
        PreparedConversationInputTurn,
    )

__all__ = ("execute_prepared_conversation_input_stream",)


async def execute_prepared_conversation_input_stream(
    api_dependencies: ApiDependencies,
    *,
    request_context: RequestContext,
    runtime: AssistantTimelineRuntime,
    session: AssistantTimelineSession,
    prepared: PreparedConversationInputTurn,
    logger: LoggerProtocol,
    on_inference_admitted: Callable[[], Awaitable[None]],
) -> None:
    effective_request = (
        dict(prepared.prepared_agent_request.final_payload)
        if prepared.prepared_agent_request is not None
        else build_inference_request_payload(prepared.request_json)
    )
    await refresh_chat_stream_usage_preview_from_inference_payload(
        runtime=runtime,
        inference_request_payload=effective_request,
        config=api_dependencies.config,
        prompt_token_counter=api_dependencies.prompt_token_counter,
        model_resolution_service=api_dependencies.model_resolution_service,
        model_information_service=api_dependencies.model_information_service,
        model_provider_coordinator=api_dependencies.model_provider_coordinator,
        virtual_model_get=api_dependencies.model_virtual_model_service.virtual_model_get,
        model_parameter_service=api_dependencies.model_parameter_service,
        plugin_manager=api_dependencies.plugin_manager,
        state_aggregator=api_dependencies.state_aggregator,
        orchestrator_lifecycle=api_dependencies.orchestrator_lifecycle,
        request_context=request_context,
        stream_transcript=session.stream_transcript,
    )

    async def commit_knowledge_claim() -> None:
        await commit_knowledge_prompt_claim_noncritical(
            api_dependencies=api_dependencies,
            claim=prepared.knowledge_prompt_claim,
            logger=logger,
            trace_id=request_context.trace_id,
        )
        await on_inference_admitted()

    if prepared.tool_context is None or prepared.prepared_agent_request is None:
        bundle = await create_streaming_inference_task(
            api_dependencies,
            context=request_context,
            request_json=effective_request,
            task_type=TASK_TYPE_CHAT_COMPLETION,
            user_id=runtime.user_id,
            owner_type="conversation",
            owner_id=runtime.conv_id,
            cancellation_id=runtime.task_cancellation_id,
            metadata=build_ws_chat_stream_task_metadata(runtime=runtime),
            request_source=REQUEST_SOURCE_WEBUI_WS,
        )
        await commit_knowledge_claim()
        await execute_timeline_non_agent_stream(
            api_dependencies,
            stream_dependencies=build_stream_dependencies(api_dependencies),
            session=session,
            context=request_context,
            bundle=bundle,
            model=runtime.model_id,
            include_usage=True,
            emit_done_marker=True,
            allow_image_events=False,
            task_lookup=lambda task_id: api_dependencies.task_registry.get(
                task_id,
                force_refresh=True,
            ),
        )
        return
    agent_request = prepared.prepared_agent_request
    await execute_conversation_agent_stream(
        api_dependencies,
        deps=build_agent_turn_engine_dependencies(
            api_dependencies=api_dependencies,
            logger=logger,
        ),
        turn_context=request_context,
        tool_context=prepared.tool_context,
        request_messages=[
            dict(message) for message in agent_request.prepared_messages_after_compaction
        ],
        request_json=dict(agent_request.final_payload),
        metadata=build_ws_chat_stream_task_metadata(runtime=runtime),
        session=session,
        agent_settings=prepared.agent_settings,
        todo_state=agent_request.todo_state,
        prepared_auto_compaction=agent_request.prepared_auto_compaction,
        request_source=REQUEST_SOURCE_WEBUI_WS,
        on_inference_admitted=commit_knowledge_claim,
        validate_visible_assistant_output=build_preview_contract_validation_callback(
            api_dependencies=api_dependencies,
            runtime=runtime,
            request_json=prepared.request_json,
        ),
        initial_output_publication_mode=(
            AgentOutputPublicationMode.VALIDATE_BEFORE_PUBLISH
            if request_requires_preview_contract(prepared.request_json)
            else AgentOutputPublicationMode.STREAM_LIVE
        ),
    )

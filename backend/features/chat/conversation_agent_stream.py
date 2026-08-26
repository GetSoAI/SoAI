"""SoAI - Canonical conversation agent stream execution [backend/features/chat/conversation_agent_stream.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.settings_types import AgentSettings
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.conversations.interaction_checkpoint import ConversationInputSuspended
from core.openai.request_fields import resolve_optional_model_name
from core.runtime.cancellation_ids import build_agent_iteration_cancellation_id
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from features.agent.runtime.claimed_prepared_stream_execution import (
    execute_claimed_prepared_stream,
)
from features.agent.runtime.prepared_stream_execution import AgentStreamingTaskBundle
from features.agent.runtime.turn_engine import AgentTurnEngineDependencies
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
)
from features.agent.runtime.turn_lifecycle.finalize import (
    resolve_exact_turn_noncritical,
)
from features.api.runtime.chat_stream_usage_preview_callback import (
    build_chat_stream_usage_preview_refresh_callback,
)
from features.assistant_timeline.agentic_outcome import resolve_agentic_terminal_outcome
from features.assistant_timeline.assistant_timeline_session import (
    AssistantTimelineSession,
)
from features.assistant_timeline.assistant_timeline_terminal import (
    finalize_agentic_stream_timeline,
)

if TYPE_CHECKING:
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.api.runtime.container.types import ApiDependencies
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = ("execute_conversation_agent_stream",)


async def execute_conversation_agent_stream(
    api_dependencies: ApiDependencies,
    *,
    deps: AgentTurnEngineDependencies,
    turn_context: RequestContext,
    tool_context: MCPToolContext,
    request_messages: list[JSONDict],
    request_json: JSONDict,
    metadata: JSONDict,
    session: AssistantTimelineSession,
    agent_settings: AgentSettings,
    todo_state: JSONDict | None,
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None,
    request_source: RequestSource,
    on_inference_admitted: Callable[[], Awaitable[None]] | None = None,
    validate_visible_assistant_output: (
        Callable[[str], Awaitable[PreviewContractOutputValidationResult]] | None
    ) = None,
    initial_output_publication_mode: AgentOutputPublicationMode | None = None,
) -> None:
    runtime = session.runtime

    async def turn_state_loader() -> JSONDict | None:
        return await resolve_exact_turn_noncritical(
            database_agent_turns=api_dependencies.database_agent_turns,
            logger=deps.logger,
            trace_id=turn_context.trace_id,
            conv_id=runtime.conv_id,
            user_id=runtime.user_id,
            turn_id=turn_context.agent_turn_id,
            request_id=runtime.request_id,
            operation="chat.conversation_agent_stream.resolve_agent_turn_state",
            log_message="Failed to resolve conversation agent turn state during finalization.",
        )

    cancellation_id = build_agent_iteration_cancellation_id(
        turn_cancellation_id=runtime.task_cancellation_id,
        iteration_index=0,
        mode=agent_settings.mode,
    )
    suspended = False
    try:
        requested_model = resolve_optional_model_name(request_json)

        async def on_claimed() -> None:
            runtime.agent_turn_id = turn_context.agent_turn_id
            runtime.agent_turn_execution_token = turn_context.agent_turn_execution_token
            runtime.agent_turn_cancellation_id = runtime.task_cancellation_id

        async def on_bytes(chunk: bytes) -> None:
            await session.consume_chunk(chunk)

        async def on_initial_bundle(bundle: AgentStreamingTaskBundle) -> None:
            async with runtime.quota_release_lock:
                runtime.active_task_id = bundle.task.task_id
                turn_context.task_id = bundle.task.task_id
                runtime.clear_quota_reservation()
            if on_inference_admitted is not None:
                await on_inference_admitted()

        await execute_claimed_prepared_stream(
            api_dependencies,
            deps=deps,
            context=turn_context,
            tool_context=tool_context,
            requested_model=requested_model,
            settings=agent_settings,
            todo_state=todo_state,
            initial_messages=request_messages,
            initial_boundary_source_messages=request_messages,
            base_request_payload=request_json,
            owner_id=runtime.conv_id,
            cancellation_id=cancellation_id,
            metadata=metadata,
            request_source=request_source,
            on_bytes=on_bytes,
            on_initial_bundle=on_initial_bundle,
            on_visible_deltas=None,
            on_inference_payload_prepared=build_chat_stream_usage_preview_refresh_callback(
                runtime=runtime,
                logger=deps.logger,
                trace_id=turn_context.trace_id,
                turn_id=turn_context.agent_turn_id,
                config=api_dependencies.config,
                prompt_token_counter=api_dependencies.prompt_token_counter,
                model_resolution_service=api_dependencies.model_resolution_service,
                model_information_service=api_dependencies.model_information_service,
                model_provider_coordinator=api_dependencies.model_provider_coordinator,
                virtual_model_get=(api_dependencies.model_virtual_model_service.virtual_model_get),
                stream_transcript=session.stream_transcript,
                model_parameter_service=api_dependencies.model_parameter_service,
                plugin_manager=api_dependencies.plugin_manager,
                state_aggregator=api_dependencies.state_aggregator,
                orchestrator_lifecycle=api_dependencies.orchestrator_lifecycle,
                request_context=turn_context,
            ),
            on_compacted_prompt_occupancy=None,
            include_usage=True,
            include_usage_in_result=False,
            summarize_messages=None,
            prepared_auto_compaction=prepared_auto_compaction,
            turn_id=turn_context.agent_turn_id,
            initial_active_inference_cancellation_id=cancellation_id,
            on_claimed=on_claimed,
            operation="chat.conversation_agent_stream.turn_cleanup",
            cancelled_log_message="Failed to finalize conversation agent turn after cancellation.",
            validate_visible_assistant_output=validate_visible_assistant_output,
            initial_output_publication_mode=initial_output_publication_mode,
        )
    except ConversationInputSuspended:
        suspended = True
        raise
    finally:
        if not suspended:
            await uncancel_then_cleanup(
                finalize_agentic_stream_timeline(
                    session,
                    turn_state_loader=turn_state_loader,
                    resolve_terminal_outcome=resolve_agentic_terminal_outcome,
                ),
            )

"""SoAI - Registered WebSocket chat stream preparation execution [backend/features/api/routes/system/events/chat_stream/start_preparation_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import CancelledError
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.conversations.assistant_turn_variant_identity import (
    AssistantTurnVariantIdentity,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.api.routes.system.events.chat_stream.start_pipeline_cleanup import (
    cleanup_registered_ws_chat_stream_start_noncritical,
)
from features.api.routes.system.events.chat_stream.start_pipeline_initialization import (
    initialize_ws_chat_stream_runtime_or_error,
)
from features.api.routes.system.events.chat_stream.start_preparation_finalization import (
    finalize_preparation_cancelled,
    finalize_preparation_error,
)
from features.api.runtime.chat_execution.contracts import PreparedChatExecutionFailure
from features.api.runtime.chat_execution.websocket_start import (
    prepare_websocket_chat_execution_start,
)
from features.assistant_timeline.assistant_placeholder_publication import (
    persist_streaming_assistant_placeholder,
)
from features.assistant_timeline.conversation_events import (
    publish_chat_stream_message_events,
)
from features.assistant_timeline.loading_error_finalization import (
    publish_initial_loading_activity,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.request_message_source import (
        AgenticRequestMessageSource,
    )
    from features.api.runtime.context import ApiContext
    from features.api.streaming.types import StreamDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("prepare_registered_ws_chat_stream_runtime",)

OPERATION_START_PREPARE = "webui_ws_chat_stream.start.prepare"


async def prepare_registered_ws_chat_stream_runtime(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    runtime: AssistantTimelineRuntime,
    request_json: JSONDict,
    identity: AssistantTurnVariantIdentity,
    message_count: int,
    canonical_history: list[JSONDict],
    extra_system_messages: tuple[str, ...],
    trace_id: str | None,
    logger: LoggerProtocol,
    agentic_message_source: AgenticRequestMessageSource | None = None,
) -> None:
    chat_streams[runtime.conv_id] = runtime
    placeholder_persisted = False
    if runtime.cancellation_requested:
        await api_context.dependencies.database_stream_cancellations.settle_local(
            conv_id=runtime.conv_id,
            user_id=runtime.user_id,
            request_id=runtime.request_id,
        )
        await cleanup_registered_ws_chat_stream_start_noncritical(
            api_context=api_context,
            chat_streams=chat_streams,
            runtime=runtime,
            trace_id=trace_id,
            logger=logger,
            delete_placeholder=False,
            release_quota=True,
        )
        await api_context.dependencies.chat_stream_registry.clear_cancellation_intent_if_same(
            user_id=runtime.user_id,
            conv_id=runtime.conv_id,
            request_id=runtime.request_id,
        )
        return
    try:
        if runtime.cancellation_requested:
            raise CancelledError
        if agentic_message_source is not None:
            request_json["messages"] = await agentic_message_source.build_provider_messages(
                canonical_history,
            )
        else:
            request_json["messages"] = canonical_history
        if runtime.cancellation_requested:
            raise CancelledError
        await persist_streaming_assistant_placeholder(
            database_messages=api_context.dependencies.webui_manager.database_messages,
            runtime=runtime,
        )
        placeholder_persisted = True
        await publish_initial_loading_activity(
            runtime=runtime,
            event_bus=api_context.dependencies.event_bus,
            database_messages=api_context.dependencies.webui_manager.database_messages,
        )
        await publish_chat_stream_message_events(
            api_context.dependencies.event_bus,
            runtime,
        )
        prepared_start = await prepare_websocket_chat_execution_start(
            request=request,
            api_context=api_context,
            request_json=request_json,
            request_id=runtime.request_id,
            user_id=runtime.user_id,
            message_index=message_count,
            assistant_at_ms=identity.assistant_at_ms,
            assistant_turn_at_ms=identity.assistant_turn_at_ms,
            model_variant_index=identity.model_variant_index,
            extra_system_messages=extra_system_messages,
            agentic_message_source=agentic_message_source,
            trace_id=trace_id,
            logger=logger,
        )
    except CancelledError:
        await uncancel_then_cleanup(
            finalize_preparation_cancelled(
                api_context=api_context,
                stream_dependencies=stream_dependencies,
                chat_streams=chat_streams,
                runtime=runtime,
                placeholder_persisted=(
                    placeholder_persisted or runtime.assistant_placeholder_persisted
                ),
                trace_id=trace_id,
                logger=logger,
            ),
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION_START_PREPARE)
        log_exception(
            logger,
            coerced,
            message="Failed to prepare WebSocket chat stream.",
            trace_id=trace_id,
            operation=OPERATION_START_PREPARE,
            level="warning",
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
        )
        await finalize_preparation_error(
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            chat_streams=chat_streams,
            runtime=runtime,
            placeholder_persisted=placeholder_persisted or runtime.assistant_placeholder_persisted,
            error_code=str(coerced.code),
            error_message=str(coerced),
            trace_id=trace_id,
            logger=logger,
        )
        return
    if isinstance(prepared_start, PreparedChatExecutionFailure):
        await finalize_preparation_error(
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            chat_streams=chat_streams,
            runtime=runtime,
            placeholder_persisted=placeholder_persisted,
            error_code=prepared_start.error_code,
            error_message=prepared_start.error_message,
            trace_id=trace_id,
            logger=logger,
        )
        return
    runtime.model_id = prepared_start.effective_model_id
    runtime.quota_key_id = prepared_start.quota_key_id
    runtime.quota_token_reservation = prepared_start.quota_token_reservation
    runtime.quota_prompt_tokens = (
        coerce_optional_non_negative_int_strict(
            (
                prepared_start.quota_token_reservation.get("prompt_tokens")
                if isinstance(prepared_start.quota_token_reservation, dict)
                else None
            ),
        )
        if prepared_start.quota_token_reservation is not None
        else None
    )
    try:
        await initialize_ws_chat_stream_runtime_or_error(
            request=request,
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            chat_streams=chat_streams,
            request_context=prepared_start.request_context,
            tool_context=prepared_start.tool_context,
            prepared_agent_request=prepared_start.prepared_agent_request,
            knowledge_prompt_claim=prepared_start.knowledge_prompt_claim,
            runtime=runtime,
            request_json=prepared_start.request_json,
            trace_id=trace_id,
            logger=logger,
        )
    except CancelledError:
        await uncancel_then_cleanup(
            finalize_preparation_cancelled(
                api_context=api_context,
                stream_dependencies=stream_dependencies,
                chat_streams=chat_streams,
                runtime=runtime,
                placeholder_persisted=runtime.assistant_placeholder_persisted,
                trace_id=trace_id,
                logger=logger,
            ),
        )
        raise

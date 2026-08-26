"""SoAI - Chat stream start execution flow [backend/features/api/routes/system/events/chat_stream/start_command_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.api.routes.system.events.chat_stream.start_failure_finalization import (
    ChatStreamStartFailureBoundary,
    build_chat_stream_start_failure_context,
    finalize_chat_stream_start_failure,
)
from features.api.routes.system.events.chat_stream.start_pipeline_registration import (
    ChatStreamStartPipelineFailure,
    register_ws_chat_stream_runtime_or_error,
)
from features.api.routes.system.events.chat_stream.start_preparation_execution import (
    prepare_registered_ws_chat_stream_runtime,
)
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.conversations.assistant_turn_variant_identity import (
        AssistantTurnVariantIdentity,
    )
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.request_message_source import (
        AgenticRequestMessageSource,
    )

__all__ = ("start_chat_stream_runtime",)


async def start_chat_stream_runtime(
    *,
    failure_boundary: ChatStreamStartFailureBoundary,
    chat_streams: dict[str, AssistantTimelineRuntime],
    request_json: JSONDict,
    identity: AssistantTurnVariantIdentity,
    message_count: int,
    extra_system_messages: tuple[str, ...],
    trace_id: str | None,
    logger: LoggerProtocol,
    agentic_message_source: AgenticRequestMessageSource | None = None,
) -> None:
    runtime = await register_ws_chat_stream_runtime_or_error(
        request=failure_boundary.request,
        api_context=failure_boundary.api_context,
        conv_id=failure_boundary.conv_id,
        request_id=failure_boundary.request_id,
        user_id=failure_boundary.user_id,
        model_id=failure_boundary.model_id,
        identity=identity,
        message_index=message_count,
        quota_key_id=None,
        quota_token_reservation=None,
        trace_id=trace_id,
        logger=logger,
    )
    if isinstance(runtime, ChatStreamStartPipelineFailure):
        failure_context = build_chat_stream_start_failure_context(
            boundary=failure_boundary,
            identity=identity,
            message_index=message_count,
        )
        await finalize_chat_stream_start_failure(
            context=failure_context,
            error_code=runtime.error_code,
            error_message=runtime.error_message,
        )
        return
    await prepare_registered_ws_chat_stream_runtime(
        request=failure_boundary.request,
        api_context=failure_boundary.api_context,
        stream_dependencies=failure_boundary.stream_dependencies,
        chat_streams=chat_streams,
        runtime=runtime,
        request_json=request_json,
        identity=identity,
        message_count=message_count,
        extra_system_messages=extra_system_messages,
        agentic_message_source=agentic_message_source,
        trace_id=trace_id,
        logger=logger,
    )

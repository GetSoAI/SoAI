"""SoAI - One durable Chat input variant execution [backend/features/chat/conversation_input_variant_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import RateLimitError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.interaction_secrets import InteractionSecretEffectUnknownError
from features.api.routes.system.events.websocket_chat_stream.completion_followups import (
    track_auto_title_generation,
)
from features.api.routes.system.events.websocket_chat_stream.finalization import (
    finalize_ws_chat_stream_cancellation_noncritical,
    finalize_ws_chat_stream_error_noncritical,
)
from features.api.runtime.chat_execution.quota import (
    ConversationTurnQuotaDenied,
    ConversationTurnQuotaReservation,
    reserve_conversation_turn_stream_quota,
)
from features.api.runtime.chat_execution.runtime_quota import (
    release_ws_chat_stream_runtime_quota_noncritical,
)
from features.api.runtime.knowledge_prompt_delivery import (
    release_knowledge_prompt_claim_noncritical,
)
from features.assistant_timeline.assistant_placeholder_publication import (
    persist_streaming_assistant_placeholder,
)
from features.assistant_timeline.assistant_timeline_session import (
    AssistantTimelineSession,
)
from features.assistant_timeline.conversation_events import (
    publish_chat_stream_message_events,
)
from features.assistant_timeline.loading_error_finalization import (
    publish_initial_loading_activity,
)
from features.assistant_timeline.status_preview_state import (
    resolve_latest_user_message_excerpt,
)
from features.chat.conversation_input_runtime import create_conversation_input_runtime
from features.chat.conversation_input_stream_arms import (
    execute_prepared_conversation_input_stream,
)
from features.chat.conversation_input_turn_preparation import (
    PreparedConversationInputTurn,
    prepare_conversation_input_turn,
)
from features.chat.conversation_stream_cancellation import (
    cancel_conversation_stream_runtime,
)
from features.chat.conversation_timeline_session import (
    create_assistant_timeline_session,
)

if TYPE_CHECKING:
    from typing import Literal

    from core.logging.protocols import TraceLogger
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.api.runtime.container.types import ApiDependencies
    from features.assistant_timeline.models import AssistantTimelineRuntime

    type InputVariantTerminalState = Literal[
        "completed",
        "failed",
        "cancelled",
        "effect_unknown",
    ]

__all__ = ("execute_conversation_input_variant",)

LOGGER_NAME = "SoAI.features.chat.conversation_input_variant_execution"
OPERATION = "chat.conversation_input.execute_variant"
OPERATION_CANCEL_AFTER_FAILURE = "chat.conversation_input.cancel_after_failure"


async def _cancel_admitted_inference_noncritical(
    api_dependencies: ApiDependencies,
    *,
    context: RequestContext,
    runtime: AssistantTimelineRuntime,
    logger: TraceLogger,
    reason: str,
) -> None:
    try:
        await cancel_conversation_stream_runtime(
            api_dependencies=api_dependencies,
            context=context,
            runtime=runtime,
            reason=reason,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to cancel admitted conversation inference after failure.",
            operation=OPERATION_CANCEL_AFTER_FAILURE,
            trace_id=context.trace_id,
            level="warning",
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
        )


async def _reserve_turn_quota(
    api_dependencies: ApiDependencies,
    *,
    user_id: int,
    prepared: PreparedConversationInputTurn,
    runtime: AssistantTimelineRuntime,
) -> None:
    quota_result = await reserve_conversation_turn_stream_quota(
        api_dependencies=api_dependencies,
        user_id=user_id,
        request_json=(
            prepared.prepared_agent_request.final_payload
            if prepared.prepared_agent_request is not None
            else prepared.request_json
        ),
        logger=get_logger(LOGGER_NAME),
    )
    if isinstance(quota_result, ConversationTurnQuotaDenied):
        raise RateLimitError(
            quota_result.message,
            details={
                "window": quota_result.window,
                "retry_at_ms": quota_result.retry_at_ms,
            },
        )
    if not isinstance(quota_result, ConversationTurnQuotaReservation):
        return
    runtime.quota_key_id = quota_result.key_id
    runtime.quota_token_reservation = quota_result.token_reservation
    if isinstance(quota_result.token_reservation, dict):
        prompt_tokens = quota_result.token_reservation.get("prompt_tokens")
        if isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool):
            runtime.quota_prompt_tokens = prompt_tokens


async def execute_conversation_input_variant(
    api_dependencies: ApiDependencies,
    *,
    input_record: JSONDict,
    claim_owner: str,
    server_boot_id: str,
) -> tuple[InputVariantTerminalState, str]:
    execution = await create_conversation_input_runtime(
        api_dependencies,
        input_record=input_record,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )
    runtime = execution.timeline
    context = execution.request_context
    session: AssistantTimelineSession | None = None
    prepared: PreparedConversationInputTurn | None = None
    inference_admitted = False
    logger = get_logger(LOGGER_NAME)
    try:
        await persist_streaming_assistant_placeholder(
            database_messages=api_dependencies.database_messages,
            runtime=runtime,
        )
        await publish_initial_loading_activity(
            runtime=runtime,
            event_bus=api_dependencies.event_bus,
            database_messages=api_dependencies.database_messages,
        )
        await publish_chat_stream_message_events(api_dependencies.event_bus, runtime)
        prepared = await prepare_conversation_input_turn(
            api_dependencies,
            request_context=context,
            conv_id=execution.conv_id,
            user_id=execution.user_id,
            model_settings_snapshot=execution.model_settings,
            message_index=runtime.message_index,
            assistant_at_ms=runtime.assistant_at_ms,
            assistant_turn_at_ms=runtime.assistant_turn_at_ms,
            model_variant_index=runtime.model_variant_index,
            request_id=runtime.request_id,
        )
        status_preview_request_json = (
            prepared.prepared_agent_request.final_payload
            if prepared.prepared_agent_request is not None
            else prepared.request_json
        )
        runtime.latest_user_message_excerpt = resolve_latest_user_message_excerpt(
            status_preview_request_json,
        )
        runtime.model_id = prepared.requested_model
        await _reserve_turn_quota(
            api_dependencies,
            user_id=execution.user_id,
            prepared=prepared,
            runtime=runtime,
        )
        session = create_assistant_timeline_session(
            api_dependencies=api_dependencies,
            runtime=runtime,
            collect_tool_calls=prepared.tool_context is not None,
            status_preview_enabled=True,
        )
        session.start()

        async def mark_inference_admitted() -> None:
            nonlocal inference_admitted
            inference_admitted = True

        await execute_prepared_conversation_input_stream(
            api_dependencies,
            request_context=context,
            runtime=runtime,
            session=session,
            prepared=prepared,
            logger=logger,
            on_inference_admitted=mark_inference_admitted,
        )
        if runtime.model_variant_index == 0:
            track_auto_title_generation(
                api_dependencies=api_dependencies,
                runtime=runtime,
                task_name=f"conversation-input-auto-title-{execution.conv_id}",
            )
        if runtime.input_terminal_state == "failed":
            return ("failed", runtime.input_terminal_code or "server_error")
        if runtime.input_terminal_state == "cancelled":
            return ("cancelled", runtime.input_terminal_code or "cancelled")
        if runtime.input_terminal_state == "effect_unknown":
            return ("effect_unknown", runtime.input_terminal_code or "effect_unknown")
        return ("completed", runtime.input_terminal_code or "completed")
    except (TaskCancelledError, asyncio.CancelledError) as exception:
        if session is None:
            session = create_assistant_timeline_session(
                api_dependencies=api_dependencies,
                runtime=runtime,
                collect_tool_calls=prepared is not None and prepared.tool_context is not None,
                status_preview_enabled=True,
            )
        runtime.cancellation_requested = True
        runtime.cancellation_reason = "Chat stream was cancelled."
        await finalize_ws_chat_stream_cancellation_noncritical(
            session=session,
            database_agent_turns=api_dependencies.database_agent_turns,
            task_registry=api_dependencies.task_registry,
            logger=logger,
            context=context,
            tool_context=prepared.tool_context if prepared is not None else None,
        )
        if isinstance(exception, asyncio.CancelledError):
            raise
        return ("cancelled", runtime.input_terminal_code or "cancelled")
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        effect_unknown = isinstance(exception, InteractionSecretEffectUnknownError)
        if not effect_unknown:
            log_exception(
                logger,
                coerced,
                message="Conversation input variant execution failed.",
                operation=OPERATION,
                trace_id=context.trace_id,
                details={"input_id": execution.input_id, "conv_id": execution.conv_id},
            )
        if inference_admitted:
            await _cancel_admitted_inference_noncritical(
                api_dependencies,
                context=context,
                runtime=runtime,
                logger=logger,
                reason=str(coerced),
            )
        if session is None:
            session = create_assistant_timeline_session(
                api_dependencies=api_dependencies,
                runtime=runtime,
                collect_tool_calls=prepared is not None and prepared.tool_context is not None,
                status_preview_enabled=True,
            )
        await finalize_ws_chat_stream_error_noncritical(
            session=session,
            database_agent_turns=api_dependencies.database_agent_turns,
            task_registry=api_dependencies.task_registry,
            logger=logger,
            context=context,
            tool_context=prepared.tool_context if prepared is not None else None,
            error_message=coerced.message,
            error_code=str(coerced.code),
            turn_error_message=str(coerced),
            turn_error_type=str(coerced.code),
        )
        if effect_unknown:
            return ("effect_unknown", "secret_tool_effect_unknown")
        return ("failed", runtime.input_terminal_code or str(coerced.code))
    finally:
        if prepared is not None and not inference_admitted:
            await uncancel_then_cleanup(
                release_knowledge_prompt_claim_noncritical(
                    api_dependencies=api_dependencies,
                    claim=prepared.knowledge_prompt_claim,
                    logger=logger,
                    trace_id=context.trace_id,
                ),
            )
        await uncancel_then_cleanup(
            release_ws_chat_stream_runtime_quota_noncritical(
                database_api_keys=api_dependencies.database_api_keys,
                runtime=runtime,
                logger=logger,
                trace_id=context.trace_id,
                operation="chat.conversation_input.release_quota",
                message="Failed to release conversation input quota.",
            ),
        )
        if session is not None:
            await uncancel_then_cleanup(session.close())
        await uncancel_then_cleanup(api_dependencies.chat_stream_registry.remove_if_same(runtime))

"""SoAI - Manual compaction background runner [backend/features/api/routes/webui/conversation_agent_compaction/runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from fastapi import Request

from core.agent.turn_state_requests import require_request_context_turn_execution_token
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.timing.epoch import epoch_ms
from features.api.routes.webui.conversation_agent_compaction.execution_identity import (
    ManualCompactionExecutionIdentity,
)
from features.api.routes.webui.conversation_agent_compaction.run_state_factory import (
    build_manual_compaction_run_state,
)
from features.api.routes.webui.conversation_agent_compaction.streaming import (
    ManualCompactionDeltaStreamer,
)
from features.api.routes.webui.conversation_agent_compaction.summarizer_pipeline import (
    build_manual_compaction_summary_text,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.webui_attachments.provider_projection import (
    project_webui_attachments_for_provider,
)
from features.api.streaming.types import StreamDependencies

__all__ = ("run_manual_compaction",)

LOGGER_NAME = "SoAI.features.api.conversation_agent_compaction_runner"
OPERATION = "webui.agent_compaction.run_manual"


async def run_manual_compaction(
    *,
    request: Request,
    api_context: ApiContext,
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    conv_id: str,
    user_id: int,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    tool_started_at_ms: int,
    model: str,
    context_window_tokens: int,
    compaction_limit: int | None,
    summarizer_budget: int,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> None:
    logger: LoggerProtocol = get_logger(LOGGER_NAME)
    try:
        turn_cancellation_id_value = context.cancellation_id
    except AttributeError:
        turn_cancellation_id_value = None
    turn_cancellation_id = str(turn_cancellation_id_value or "").strip() or None
    execution_token = require_request_context_turn_execution_token(
        context,
        operation=OPERATION,
    )
    execution_identity = ManualCompactionExecutionIdentity(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        iteration_index=iteration_index,
        tool_call_id=tool_call_id,
        tool_started_at_ms=tool_started_at_ms,
    )
    delta_streamer = ManualCompactionDeltaStreamer(
        api_context=api_context,
        logger=logger,
        conv_id=conv_id,
        user_id=user_id,
        turn_cancellation_id=turn_cancellation_id,
    )
    run_state = build_manual_compaction_run_state(
        api_context=api_context,
        logger=logger,
        identity=execution_identity,
        execution_token=execution_token,
        turn_cancellation_id=turn_cancellation_id,
        model=model,
        context_window_tokens=context_window_tokens,
        compaction_limit=compaction_limit,
        summarizer_budget=summarizer_budget,
        source_messages=[],
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
    )

    try:
        await delta_streamer.raise_if_cancelled()
        canonical_source_messages = (
            await api_context.dependencies.database_messages.get_canonical_agent_history(
                conv_id,
                user_id,
                before_timestamp_exclusive=replace_assistant_at_ms,
            )
        )
        if canonical_source_messages is None:
            raise ValidationError("Conversation not found or access denied.")
        provider_source_messages = await project_webui_attachments_for_provider(
            dependencies=api_context.dependencies,
            conv_id=conv_id,
            user_id=user_id,
            model_id=model,
            messages=canonical_source_messages,
        )
        run_state = build_manual_compaction_run_state(
            api_context=api_context,
            logger=logger,
            identity=execution_identity,
            execution_token=execution_token,
            turn_cancellation_id=turn_cancellation_id,
            model=model,
            context_window_tokens=context_window_tokens,
            compaction_limit=compaction_limit,
            summarizer_budget=summarizer_budget,
            source_messages=canonical_source_messages,
            replace_assistant_at_ms=replace_assistant_at_ms,
            replace_tool_call_id=replace_tool_call_id,
        )
        if not canonical_source_messages:
            empty_message = "Conversation is empty; nothing to compact."
            completed_at_ms = int(epoch_ms())
            tool_result_details = await run_state.resolve_tool_result_details(None)
            await run_state.finalize_success(
                completed_at_ms=completed_at_ms,
                activity_output_text=empty_message,
                activity_prompt_message=None,
                tool_result_details=tool_result_details,
            )
            return
        await delta_streamer.raise_if_cancelled()
        summary = await build_manual_compaction_summary_text(
            request=request,
            api_context=api_context,
            stream_dependencies=stream_dependencies,
            context=context,
            conv_id=conv_id,
            model=model,
            source_messages=provider_source_messages,
            compaction_limit=compaction_limit,
            summarizer_budget=summarizer_budget,
            raise_if_cancelled=delta_streamer.raise_if_cancelled,
            on_text_delta=delta_streamer.on_text_delta,
        )
        await delta_streamer.raise_if_cancelled()
        completed_at_ms = int(epoch_ms())
        tool_result_details = await run_state.resolve_tool_result_details(summary)
        await run_state.finalize_success(
            completed_at_ms=completed_at_ms,
            activity_output_text=summary.summary_text,
            activity_prompt_message=summary.prompt_message,
            tool_result_details=tool_result_details,
        )
    except asyncio.CancelledError:
        completed_at_ms = int(epoch_ms())
        tool_result_details = await run_state.resolve_tool_result_details(None)
        await run_state.finalize_failure(
            completed_at_ms=completed_at_ms,
            failure_status="cancelled",
            activity_output_text="Context compaction cancelled.",
            activity_prompt_message=None,
            error_message="Manual compaction was cancelled.",
            error_type="cancelled",
            tool_result_details=tool_result_details,
        )
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message="Manual compaction failed.",
            operation=OPERATION,
            level="error",
        )
        completed_at_ms = int(epoch_ms())
        tool_result_details = await run_state.resolve_tool_result_details(None)
        await run_state.finalize_failure(
            completed_at_ms=completed_at_ms,
            failure_status="error",
            activity_output_text="Context compaction failed.",
            activity_prompt_message=None,
            error_message=coerced.message,
            error_type=str(coerced.code),
            tool_result_details=tool_result_details,
        )

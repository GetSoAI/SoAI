"""SoAI - Agentic SSE engine shared by API and WebUI [backend/features/api/streaming/agentic_sse_engine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ConflictError, SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.openai.sse_events import format_openai_stream_error_chunk
from core.openai.sse_frames import sse_done_chunk
from core.orchestrator.types import MCPToolContext
from core.runtime.request_context import RequestContext
from features.agent.runtime.streaming_turn_engine import run_streaming_turn
from features.agent.runtime.turn_engine import resolve_existing_turn_id

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.openai.token_accounting import PromptOccupancy
    from core.openai.usage.models import CanonicalUsage
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentStreamingInferenceRunnerProtocol
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.agent.runtime.execution_preparation import AgentRuntimePreparation
    from features.agent.runtime.turn_iteration_policy_types import (
        AgentOutputPublicationMode,
    )
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = ("run_agentic_sse_engine",)

OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE = "api_openai.agentic_stream.engine"
OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE_DONE_SENTINEL = (
    "api_openai.agentic_stream.engine.done_sentinel"
)


async def run_agentic_sse_engine(
    *,
    context: RequestContext,
    trace_id: str,
    logger: TraceLogger,
    format_error_chunk: Callable[[str, str, str], str] | None,
    base_request_payload: JSONDict,
    tool_context: MCPToolContext,
    runtime_preparation: AgentRuntimePreparation,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    streaming_inference_runner: AgentStreamingInferenceRunnerProtocol,
    on_inference_payload_prepared: Callable[[JSONDict], Awaitable[None] | None] | None,
    on_pre_compaction_prompt_occupancy: Callable[[PromptOccupancy], None] | None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None,
    on_visible_usage_resolved: Callable[[CanonicalUsage], Awaitable[None] | None] | None,
    include_usage: bool,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    first_iteration_cancellation_id: str | None,
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None,
    validate_visible_assistant_output: (
        Callable[
            [str],
            Awaitable[PreviewContractOutputValidationResult],
        ]
        | None
    ),
    initial_output_publication_mode: AgentOutputPublicationMode | None,
    detach_event: asyncio.Event,
    push_bytes: Callable[[bytes], Awaitable[None]],
) -> None:
    done_sentinel_pushed = False
    try:
        await run_streaming_turn(
            deps=runtime_preparation.deps,
            context=context,
            tool_context=tool_context,
            initial_messages=message_history,
            initial_boundary_source_messages=boundary_source_messages,
            base_request_payload=base_request_payload,
            settings=runtime_preparation.settings,
            streaming_inference_runner=streaming_inference_runner,
            on_bytes=push_bytes,
            on_inference_payload_prepared=on_inference_payload_prepared,
            on_pre_compaction_prompt_occupancy=on_pre_compaction_prompt_occupancy,
            on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
            on_visible_usage_resolved=on_visible_usage_resolved,
            include_usage=include_usage,
            summarize_messages=summarize_messages,
            first_iteration_cancellation_id=first_iteration_cancellation_id,
            prepared_auto_compaction=prepared_auto_compaction,
            turn_id=resolve_existing_turn_id(context),
            validate_visible_assistant_output=validate_visible_assistant_output,
            initial_output_publication_mode=initial_output_publication_mode,
        )
        done_sentinel_pushed = True
    except asyncio.CancelledError:
        done_sentinel_pushed = True
        raise
    except ConflictError as exception:
        error_bytes = format_openai_stream_error_chunk(
            format_error_chunk,
            str(exception) or "Agent turn conflict.",
            "conflict_error",
            trace_id,
        )
        await push_bytes(error_bytes)
        await push_bytes(sse_done_chunk())
        done_sentinel_pushed = True
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="api_openai.agentic_stream.engine",
        )
        log_exception(
            logger,
            coerced,
            message="Agentic stream engine failed.",
            trace_id=trace_id,
            operation=OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE,
            level="error",
        )
        await _emit_engine_failure_response(
            trace_id=trace_id,
            format_error_chunk=format_error_chunk,
            detach_event=detach_event,
            push_bytes=push_bytes,
        )
        done_sentinel_pushed = True
    except SoAIError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Agentic stream engine failed.",
            trace_id=trace_id,
            operation=OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE,
            level="warning",
        )
        await _emit_engine_failure_response(
            trace_id=trace_id,
            format_error_chunk=format_error_chunk,
            detach_event=detach_event,
            push_bytes=push_bytes,
        )
        done_sentinel_pushed = True
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="api_openai.agentic_stream.engine",
        )
        log_exception(
            logger=logger,
            exception=coerced,
            message="Agentic stream engine failed with unexpected error.",
            trace_id=trace_id,
            operation=OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE,
            level="error",
        )
        await _emit_engine_failure_response(
            trace_id=trace_id,
            format_error_chunk=format_error_chunk,
            detach_event=detach_event,
            push_bytes=push_bytes,
        )
        done_sentinel_pushed = True
    finally:
        if not done_sentinel_pushed and not detach_event.is_set():
            try:
                await push_bytes(sse_done_chunk())
            except asyncio.CancelledError as sentinel_exception:
                raise_cancelled_error(sentinel_exception)
            except RECOVERABLE_EXCEPTIONS as sentinel_exception:
                coerced_sentinel = coerce_to_soai_error(
                    sentinel_exception,
                    operation="api_openai.agentic_stream.engine.done_sentinel",
                )
                log_handled_exception(
                    logger,
                    coerced_sentinel,
                    message="Failed to push [DONE] sentinel in engine finally block (non-critical).",
                    operation=OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE_DONE_SENTINEL,
                    level="debug",
                )
            except SoAIError as sentinel_exception:
                log_handled_exception(
                    logger,
                    sentinel_exception,
                    message="Failed to push [DONE] sentinel in engine finally block (non-critical).",
                    operation=OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE_DONE_SENTINEL,
                    level="debug",
                )
            except UNEXPECTED_RUNTIME_EXCEPTIONS as sentinel_exception:
                coerced_sentinel = coerce_to_soai_error(
                    sentinel_exception,
                    operation="api_openai.agentic_stream.engine.done_sentinel",
                )
                log_handled_exception(
                    logger,
                    coerced_sentinel,
                    message="Failed to push [DONE] sentinel due to unexpected exception (non-critical).",
                    operation=OPERATION_API_OPENAI_AGENTIC_STREAM_ENGINE_DONE_SENTINEL,
                    level="debug",
                )


async def _emit_engine_failure_response(
    *,
    trace_id: str,
    format_error_chunk: Callable[[str, str, str], str] | None,
    detach_event: asyncio.Event,
    push_bytes: Callable[[bytes], Awaitable[None]],
) -> None:
    if detach_event.is_set():
        return
    error_bytes = format_openai_stream_error_chunk(
        format_error_chunk,
        "Internal server error.",
        "server_error",
        trace_id,
    )
    await push_bytes(error_bytes)
    await push_bytes(sse_done_chunk())

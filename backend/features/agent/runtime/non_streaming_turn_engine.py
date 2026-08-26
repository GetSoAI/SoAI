"""SoAI - Agent non-streaming turn engine [backend/features/agent/runtime/non_streaming_turn_engine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_COMPLETED
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.openai.internal_retry_prompt import is_internal_retry_output_leak
from features.agent.runtime.inference_request_payload import (
    build_turn_inference_request_payload_for_iteration,
)
from features.agent.runtime.injected_prompt_echo_stripping import (
    strip_echoed_injected_prompt_blocks,
)
from features.agent.runtime.non_streaming_contract_recovery import (
    build_non_streaming_contract_recovery_result,
)
from features.agent.runtime.non_streaming_inference_results import (
    build_successful_non_streaming_inference_result,
)
from features.agent.runtime.non_streaming_terminal_replay import (
    raise_for_non_streaming_terminal_replay,
)
from features.agent.runtime.non_streaming_turn_events import (
    publish_assistant_item_events,
)
from features.agent.runtime.openai_payload import (
    extract_assistant_content_visible,
    remove_suppressed_assistant_tool_calls,
    replace_assistant_content_visible,
)
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
)
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult
from features.agent.runtime.turn_runtime_execution import execute_agent_turn_runtime

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
    from features.agent.runtime.turn_engine import (
        AgentTurnEngineDependencies,
        AgentTurnResult,
    )

__all__ = ("run_non_streaming_turn",)

OPERATION_NON_STREAMING_INFERENCE = "agent.non_streaming_turn.run_inference"


async def run_non_streaming_turn(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    initial_messages: list[JSONDict],
    initial_boundary_source_messages: list[JSONDict],
    base_request_payload: JSONDict,
    settings: AgentSettings,
    make_inference_request: Callable[[int, JSONDict, str], Awaitable[JSONDict]],
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None = None,
    prepared_auto_compaction: PreparedAutoCompactionSnapshot | None = None,
    turn_id: str | None = None,
) -> AgentTurnResult:
    async def run_inference(
        iteration_index: int,
        cancellation_id: str,
        current_history: list[JSONDict],
        suppress_tools: bool,
        output_publication_mode: AgentOutputPublicationMode,
        bootstrap: AgentTurnBootstrap,
    ) -> TurnLoopInferenceResult:
        request_payload = await build_turn_inference_request_payload_for_iteration(
            deps,
            context,
            bootstrap,
            base_request_payload,
            current_history,
            suppress_tools,
        )
        try:
            payload = await make_inference_request(
                iteration_index,
                request_payload,
                cancellation_id,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_NON_STREAMING_INFERENCE,
            )
            log_exception(
                deps.logger,
                coerced,
                message="Agent non-streaming inference request failed.",
                operation=OPERATION_NON_STREAMING_INFERENCE,
            )
            recovered = build_non_streaming_contract_recovery_result(coerced)
            if recovered is not None:
                return recovered
            return _build_failed_inference_result(coerced)
        assistant_text = _sanitize_assistant_text(
            payload=payload,
            output_publication_mode=output_publication_mode,
            logger=deps.logger,
        )
        if suppress_tools:
            remove_suppressed_assistant_tool_calls(payload, assistant_text=assistant_text)
        await publish_assistant_item_events(
            emit_event=bootstrap.emit_event,
            user_id=bootstrap.primitives.user_id,
            conv_id=bootstrap.primitives.conv_id,
            turn_id=bootstrap.primitives.turn_id,
            iteration_index=iteration_index,
            next_action_sequence=bootstrap.sequence_tracker.next_sequence,
            assistant_text=assistant_text,
        )
        return _build_successful_inference_result(payload=payload, assistant_text=assistant_text)

    runtime_execution = await execute_agent_turn_runtime(
        deps=deps,
        context=context,
        tool_context=tool_context,
        initial_messages=initial_messages,
        initial_boundary_source_messages=initial_boundary_source_messages,
        base_request_payload=base_request_payload,
        settings=settings,
        summarize_messages=summarize_messages,
        run_inference=run_inference,
        prepared_auto_compaction=prepared_auto_compaction,
        turn_id=turn_id,
        initial_active_inference_cancellation_id=None,
        operation="agent.non_streaming_turn.run_non_streaming_turn",
        include_usage_in_result=True,
    )
    persisted_terminal_turn_replay = runtime_execution.persisted_terminal_turn_replay
    if persisted_terminal_turn_replay is not None and (
        persisted_terminal_turn_replay.status != AGENT_TURN_STATUS_COMPLETED
        or not runtime_execution.result.final_payload
    ):
        raise_for_non_streaming_terminal_replay(persisted_terminal_turn_replay)
    return runtime_execution.result


def _sanitize_assistant_text(
    *,
    payload: JSONDict,
    output_publication_mode: AgentOutputPublicationMode,
    logger: LoggerProtocol,
) -> str:
    assistant_text = extract_assistant_content_visible(payload)
    stripping = strip_echoed_injected_prompt_blocks(assistant_text)
    if stripping.stripped:
        logger.warning(
            "Stripped injected prompt echo from assistant output (tags=%s, removed_chars=%d).",
            ",".join(stripping.stripped_tags),
            max(0, len(assistant_text) - len(stripping.sanitized_text)),
        )
        assistant_text = stripping.sanitized_text
        replace_assistant_content_visible(payload, assistant_text)
    if (
        output_publication_mode is AgentOutputPublicationMode.VALIDATE_BEFORE_PUBLISH
        and is_internal_retry_output_leak(assistant_text)
    ):
        logger.warning("Suppressed internal retry prompt leak from assistant output.")
        assistant_text = ""
        replace_assistant_content_visible(payload, assistant_text)
    return assistant_text


def _build_failed_inference_result(error: SoAIError) -> TurnLoopInferenceResult:
    return TurnLoopInferenceResult(
        payload=None,
        assistant_text=None,
        finish_reason=None,
        usage=None,
        stream_id=None,
        successful=False,
        error_message=error.message,
        error_type=str(error.code),
        assistant_output_published=False,
        tool_calls=[],
        visible_text_chars=0,
        thinking_text_chars=0,
        error_details=error.details,
    )


def _build_successful_inference_result(
    *,
    payload: JSONDict,
    assistant_text: str,
) -> TurnLoopInferenceResult:
    return build_successful_non_streaming_inference_result(
        payload=payload,
        assistant_text=assistant_text,
        include_usage=True,
    )

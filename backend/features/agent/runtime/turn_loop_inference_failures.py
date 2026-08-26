"""SoAI - Agent turn-loop inference failure recovery [backend/features/agent/runtime/turn_loop_inference_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_CANCELLED,
    AGENT_TURN_STATUS_ERROR,
)
from core.errors.error_types import ErrorType
from core.errors.exceptions import ValidationError
from core.openai.request_requirement_failures import (
    classify_openai_request_requirement_mismatch,
)
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from core.types.json import JSONDict
from features.agent.runtime.streaming_inference_runner import (
    INFERENCE_ADMISSION_UNAVAILABLE_ERROR_TYPE,
)
from features.agent.runtime.tool_image_relay_messages import (
    is_tool_image_relay_message,
)
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult
from features.agent.runtime.turn_terminal_state import TurnTerminalOutcome

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "TurnLoopInferenceFailureResolution",
    "TurnLoopInferenceFailureTransition",
    "resolve_turn_loop_inference_failure",
    "resolve_turn_loop_inference_failure_transition",
)


@dataclass(frozen=True, slots=True)
class TurnLoopInferenceFailureResolution:
    should_retry: bool
    final_status: str | None
    final_error_message: str | None
    final_error_type: str | None


@dataclass(frozen=True, slots=True)
class TurnLoopInferenceFailureTransition:
    should_retry: bool
    relay_retry_attempted: bool
    terminal_outcome: TurnTerminalOutcome | None
    final_text: str | None
    inference_admission_retries: int
    delay_seconds: float

    def require_terminal_outcome(self) -> TurnTerminalOutcome:
        if self.terminal_outcome is None:
            raise ValidationError("Inference failure transition requires a terminal outcome.")
        return self.terminal_outcome


def resolve_turn_loop_inference_failure(
    *,
    inference: TurnLoopInferenceResult,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    relay_retry_attempted: bool,
) -> TurnLoopInferenceFailureResolution:
    if (
        (not relay_retry_attempted)
        and _has_trailing_tool_image_relay_message(message_history)
        and classify_openai_request_requirement_mismatch(
            message=inference.error_message,
            details=inference.error_details,
        )
        is not None
        and _drop_trailing_tool_image_relay_message(message_history) > 0
    ):
        _drop_trailing_tool_image_relay_message(boundary_source_messages)
        return TurnLoopInferenceFailureResolution(
            should_retry=True,
            final_status=None,
            final_error_message=None,
            final_error_type=None,
        )
    return TurnLoopInferenceFailureResolution(
        should_retry=False,
        final_status=(
            AGENT_TURN_STATUS_CANCELLED
            if inference.error_type == AGENT_TURN_STATUS_CANCELLED
            else AGENT_TURN_STATUS_ERROR
        ),
        final_error_message=inference.error_message or "Agent turn failed.",
        final_error_type=inference.error_type or "server_error",
    )


def resolve_turn_loop_inference_failure_transition(
    *,
    inference: TurnLoopInferenceResult,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    relay_retry_attempted: bool,
    inference_admission_retries: int,
    max_inference_admission_retries: int,
    logger: LoggerProtocol,
) -> TurnLoopInferenceFailureTransition:
    if inference.error_type == INFERENCE_ADMISSION_UNAVAILABLE_ERROR_TYPE:
        return _resolve_admission_failure_transition(
            inference_admission_retries=inference_admission_retries,
            max_inference_admission_retries=max_inference_admission_retries,
            relay_retry_attempted=relay_retry_attempted,
            logger=logger,
        )
    failure = resolve_turn_loop_inference_failure(
        inference=inference,
        message_history=message_history,
        boundary_source_messages=boundary_source_messages,
        relay_retry_attempted=relay_retry_attempted,
    )
    if failure.should_retry:
        logger.warning(
            "Retrying agent turn iteration without tool image relay after capability mismatch.",
        )
        return TurnLoopInferenceFailureTransition(
            should_retry=True,
            relay_retry_attempted=True,
            terminal_outcome=None,
            final_text=None,
            inference_admission_retries=inference_admission_retries,
            delay_seconds=0.0,
        )
    return TurnLoopInferenceFailureTransition(
        should_retry=False,
        relay_retry_attempted=relay_retry_attempted,
        terminal_outcome=_resolve_failed_inference_terminal_outcome(failure),
        final_text=inference.assistant_text if inference.assistant_output_published else None,
        inference_admission_retries=inference_admission_retries,
        delay_seconds=0.0,
    )


def _resolve_admission_failure_transition(
    *,
    inference_admission_retries: int,
    max_inference_admission_retries: int,
    relay_retry_attempted: bool,
    logger: LoggerProtocol,
) -> TurnLoopInferenceFailureTransition:
    if inference_admission_retries < max_inference_admission_retries:
        delay_seconds = compute_exponential_backoff_seconds(
            inference_admission_retries,
            base_seconds=1.0,
            maximum_seconds=10.0,
            jitter_ratio=0.2,
        )
        logger.warning(
            "Retrying agent turn iteration after inference admission backpressure (attempt=%d, delay_seconds=%.3f).",
            inference_admission_retries + 1,
            delay_seconds,
        )
        return TurnLoopInferenceFailureTransition(
            should_retry=True,
            relay_retry_attempted=relay_retry_attempted,
            terminal_outcome=None,
            final_text=None,
            inference_admission_retries=inference_admission_retries + 1,
            delay_seconds=delay_seconds,
        )
    logger.warning(
        "Agent turn terminating after exhausting inference admission retries (max=%d).",
        max_inference_admission_retries,
    )
    return TurnLoopInferenceFailureTransition(
        should_retry=False,
        relay_retry_attempted=relay_retry_attempted,
        terminal_outcome=TurnTerminalOutcome(
            status=AGENT_TURN_STATUS_ERROR,
            error_message="Inference capacity is temporarily unavailable, please retry.",
            error_type=ErrorType.SERVICE_UNAVAILABLE.value,
        ),
        final_text=None,
        inference_admission_retries=inference_admission_retries,
        delay_seconds=0.0,
    )


def _resolve_failed_inference_terminal_outcome(
    failure: TurnLoopInferenceFailureResolution,
) -> TurnTerminalOutcome:
    if failure.final_status is None:
        raise ValidationError("Agent turn failure resolution missing final status.")
    return TurnTerminalOutcome(
        status=failure.final_status,
        error_message=failure.final_error_message,
        error_type=failure.final_error_type,
    )


def _has_trailing_tool_image_relay_message(
    message_history: list[JSONDict],
) -> bool:
    if not message_history:
        return False
    return is_tool_image_relay_message(message_history[-1])


def _drop_trailing_tool_image_relay_message(
    message_history: list[JSONDict],
) -> int:
    removed = 0
    while message_history and is_tool_image_relay_message(message_history[-1]):
        message_history.pop()
        removed += 1
    return removed

"""SoAI - Agent turn loop failed inference transition [backend/features/agent/runtime/turn_loop_failed_inference.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from features.agent.runtime.turn_loop_inference_failures import (
    resolve_turn_loop_inference_failure_transition,
)
from features.agent.runtime.turn_loop_retry_wait import wait_turn_retry_delay
from features.agent.runtime.turn_terminal_state import build_cancelled_turn_terminal_outcome

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult
    from features.agent.runtime.turn_terminal_state import TurnTerminalOutcome

__all__ = (
    "FailedInferenceTransition",
    "resolve_failed_inference_transition",
)


@dataclass(frozen=True, slots=True)
class FailedInferenceTransition:
    should_retry: bool
    relay_retry_attempted: bool
    inference_admission_retries: int
    terminal_outcome: TurnTerminalOutcome | None
    final_text: str | None


async def resolve_failed_inference_transition(
    *,
    inference: TurnLoopInferenceResult,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    relay_retry_attempted: bool,
    inference_admission_retries: int,
    max_inference_admission_retries: int,
    logger: LoggerProtocol,
    turn_cancelled: Callable[[], Awaitable[bool]],
) -> FailedInferenceTransition:
    failure_transition = resolve_turn_loop_inference_failure_transition(
        inference=inference,
        message_history=message_history,
        boundary_source_messages=boundary_source_messages,
        relay_retry_attempted=relay_retry_attempted,
        inference_admission_retries=inference_admission_retries,
        max_inference_admission_retries=max_inference_admission_retries,
        logger=logger,
    )
    if failure_transition.should_retry:
        if failure_transition.delay_seconds > 0:
            cancelled_during_retry_wait = await wait_turn_retry_delay(
                delay_seconds=failure_transition.delay_seconds,
                turn_cancelled=turn_cancelled,
            )
            if cancelled_during_retry_wait:
                return FailedInferenceTransition(
                    should_retry=False,
                    relay_retry_attempted=failure_transition.relay_retry_attempted,
                    inference_admission_retries=failure_transition.inference_admission_retries,
                    terminal_outcome=build_cancelled_turn_terminal_outcome(),
                    final_text=None,
                )
        return FailedInferenceTransition(
            should_retry=True,
            relay_retry_attempted=failure_transition.relay_retry_attempted,
            inference_admission_retries=failure_transition.inference_admission_retries,
            terminal_outcome=None,
            final_text=None,
        )
    return FailedInferenceTransition(
        should_retry=False,
        relay_retry_attempted=failure_transition.relay_retry_attempted,
        inference_admission_retries=failure_transition.inference_admission_retries,
        terminal_outcome=failure_transition.require_terminal_outcome(),
        final_text=failure_transition.final_text,
    )

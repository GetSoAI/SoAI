"""SoAI - Agent turn-loop terminal outcome resolution [backend/features/agent/runtime/turn_loop_terminal_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_ERROR
from features.agent.runtime.turn_terminal_state import TurnTerminalOutcome

if TYPE_CHECKING:
    from features.agent.runtime.turn_iteration_policy_types import TurnIterationDecision

__all__ = ("resolve_post_inference_terminal_outcome",)


def resolve_post_inference_terminal_outcome(
    decision: TurnIterationDecision,
) -> TurnTerminalOutcome:
    return TurnTerminalOutcome(
        status=decision.terminal_status or AGENT_TURN_STATUS_ERROR,
        error_message=decision.terminal_error_message,
        error_type=decision.terminal_error_type,
        reached_max_iterations=decision.reached_max_iterations,
    )

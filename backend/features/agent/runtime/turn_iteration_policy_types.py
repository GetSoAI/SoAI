"""SoAI - Agent turn iteration policy types [backend/features/agent/runtime/turn_iteration_policy_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from core.types.json import JSONDict

__all__ = (
    "FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION",
    "FINISH_REASON_TOOL_CALL_PROTOCOL_VIOLATION",
    "FINISH_REASON_TOOL_SEQUENCE_CONTRACT_VIOLATION",
    "AgentOutputPublicationMode",
    "PostInferenceControl",
    "TurnIterationAction",
    "TurnIterationDecision",
    "TurnIterationPolicyConfig",
    "TurnIterationPolicyState",
    "can_start_next_iteration",
    "is_next_iteration_blocked",
)

FINISH_REASON_TOOL_SEQUENCE_CONTRACT_VIOLATION: str = "soai_tool_sequence_contract_violation"
FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION: str = (
    "soai_invalid_tool_call_json_contract_violation"
)
FINISH_REASON_TOOL_CALL_PROTOCOL_VIOLATION: str = "soai_tool_call_protocol_violation"


class PostInferenceControl(Enum):
    PROCEED_TOOLS = auto()
    COMPLETE = auto()
    RETRY = auto()
    TERMINATE = auto()


class AgentOutputPublicationMode(Enum):
    STREAM_LIVE = auto()
    VALIDATE_BEFORE_PUBLISH = auto()


@dataclass(frozen=True, slots=True)
class TurnIterationPolicyState:
    empty_output_retries: int
    empty_output_silent_retries: int
    length_finish_reason_retries: int
    tool_sequence_retries: int
    invalid_tool_call_json_retries: int
    tool_call_protocol_retries: int
    tool_call_protocol_retry_signature: str
    preview_contract_retries: int


@dataclass(frozen=True, slots=True)
class TurnIterationPolicyConfig:
    max_iterations: int
    max_empty_output_retries: int
    max_empty_output_silent_retries: int
    max_length_finish_reason_retries: int
    length_finish_reason_retries_enabled: bool
    max_tool_sequence_retries: int
    max_invalid_tool_call_json_retries: int
    max_tool_call_protocol_retries: int
    max_preview_contract_retries: int


class TurnIterationAction(Enum):
    PROCEED_TOOLS = auto()
    COMPLETE = auto()
    RETRY_SILENT = auto()
    RETRY_REQUIRED_VISIBLE_OUTPUT = auto()
    TERMINAL_EMPTY_RESPONSE = auto()
    TERMINAL_MAX_ITERATIONS = auto()
    TERMINAL_TOOL_SEQUENCE_CONTRACT_VIOLATION = auto()
    TERMINAL_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION = auto()
    TERMINAL_PREVIEW_CONTRACT_VIOLATION = auto()


@dataclass(frozen=True, slots=True)
class TurnIterationDecision:
    action: TurnIterationAction
    next_state: TurnIterationPolicyState
    retry_message: JSONDict | None
    reached_max_iterations: bool
    terminal_status: str | None
    terminal_error_message: str | None
    terminal_error_type: str | None
    next_output_publication_mode: AgentOutputPublicationMode
    suppress_tools_for_next_iteration: bool = False

    @property
    def control(self) -> PostInferenceControl:
        match self.action:
            case TurnIterationAction.PROCEED_TOOLS:
                return PostInferenceControl.PROCEED_TOOLS
            case TurnIterationAction.COMPLETE:
                return PostInferenceControl.COMPLETE
            case (
                TurnIterationAction.RETRY_SILENT | TurnIterationAction.RETRY_REQUIRED_VISIBLE_OUTPUT
            ):
                return PostInferenceControl.RETRY
            case (
                TurnIterationAction.TERMINAL_EMPTY_RESPONSE
                | TurnIterationAction.TERMINAL_MAX_ITERATIONS
                | TurnIterationAction.TERMINAL_TOOL_SEQUENCE_CONTRACT_VIOLATION
                | TurnIterationAction.TERMINAL_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION
                | TurnIterationAction.TERMINAL_PREVIEW_CONTRACT_VIOLATION
            ):
                return PostInferenceControl.TERMINATE


def can_start_next_iteration(*, iteration_index: int, max_iterations: int) -> bool:
    return (iteration_index + 1) < max_iterations


def is_next_iteration_blocked(*, iteration_index: int, max_iterations: int) -> bool:
    return not can_start_next_iteration(
        iteration_index=iteration_index,
        max_iterations=max_iterations,
    )

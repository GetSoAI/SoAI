"""SoAI - Agent turn loop result types [backend/features/agent/runtime/turn_loop_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.openai.usage.models import CanonicalUsage
from core.types.json import JSONDict
from features.agent.runtime.turn_terminal_state import (
    TurnTerminalOutcome,
    TurnTerminalSnapshot,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from features.agent.runtime.turn_iteration_policy_types import (
        AgentOutputPublicationMode,
    )
    from features.api.runtime.preview_contract_output_validation import (
        PreviewContractOutputValidationResult,
    )

__all__ = (
    "TurnLoopCompactionResult",
    "TurnLoopInferenceResult",
    "TurnLoopResult",
)


@dataclass(frozen=True, slots=True)
class TurnLoopCompactionResult:
    prompt_messages: list[JSONDict]
    boundary_source_messages: list[JSONDict]


if TYPE_CHECKING:
    type TurnLoopCompactionCallback = Callable[
        [int, list[JSONDict], list[JSONDict]],
        Awaitable[TurnLoopCompactionResult],
    ]


@dataclass(frozen=True, slots=True)
class TurnLoopInferenceResult:
    payload: JSONDict | None
    assistant_text: str | None
    finish_reason: str | None
    usage: CanonicalUsage | None
    stream_id: str | None
    successful: bool
    error_message: str | None
    error_type: str | None
    assistant_output_published: bool
    tool_calls: list[JSONDict]
    visible_text_chars: int
    thinking_text_chars: int
    error_details: JSONDict | None = None
    detected_tool_calls: list[JSONDict] = field(default_factory=list[JSONDict])


if TYPE_CHECKING:
    type TurnLoopRunInferenceCallback = Callable[
        [int, str, list[JSONDict], bool, AgentOutputPublicationMode],
        Awaitable[TurnLoopInferenceResult],
    ]

    type TurnLoopVisibleAssistantValidator = Callable[
        [str],
        Awaitable[PreviewContractOutputValidationResult],
    ] | None


@dataclass(frozen=True, slots=True)
class TurnLoopResult:
    final_payload: JSONDict
    final_text: str | None
    usage_aggregate: CanonicalUsage | None
    stream_id: str | None
    iteration_index: int
    total_tool_calls: int
    terminal_outcome: TurnTerminalOutcome

    @property
    def reached_max_iterations(self) -> bool:
        return self.terminal_outcome.reached_max_iterations

    @property
    def final_status(self) -> str:
        return self.terminal_outcome.status

    @property
    def final_error_message(self) -> str | None:
        return self.terminal_outcome.error_message

    @property
    def final_error_type(self) -> str | None:
        return self.terminal_outcome.error_type

    @property
    def preserve_active_subagents(self) -> bool:
        return self.terminal_outcome.preserve_active_subagents

    @property
    def terminal_snapshot(self) -> TurnTerminalSnapshot:
        return TurnTerminalSnapshot(
            iteration_index=self.iteration_index,
            assistant_text=self.final_text,
            reached_max_iterations=self.terminal_outcome.reached_max_iterations,
        )

"""SoAI - Agent turn loop outcome accumulation [backend/features/agent/runtime/turn_loop_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field

from core.openai.usage.models import CanonicalUsage
from core.openai.usage.resolution import aggregate_canonical_usage
from core.types.json import JSONDict, JSONValue
from features.agent.runtime.turn_loop_models import TurnLoopInferenceResult, TurnLoopResult
from features.agent.runtime.turn_terminal_state import (
    TurnTerminalOutcome,
    build_completed_turn_terminal_outcome,
)

__all__ = ("TurnLoopOutcome",)


@dataclass(slots=True)
class TurnLoopOutcome:
    final_payload: JSONDict = field(default_factory=dict[str, JSONValue])
    final_text: str | None = None
    usage_aggregate: CanonicalUsage | None = None
    stream_id: str | None = None
    terminal_outcome: TurnTerminalOutcome = field(
        default_factory=build_completed_turn_terminal_outcome,
    )

    def record_inference(self, inference: TurnLoopInferenceResult) -> None:
        if inference.stream_id is not None and self.stream_id is None:
            self.stream_id = inference.stream_id
        self.usage_aggregate = aggregate_canonical_usage(
            self.usage_aggregate,
            inference.usage,
        )

    def build_result(self, *, iteration_index: int, total_tool_calls: int) -> TurnLoopResult:
        return TurnLoopResult(
            final_payload=self.final_payload,
            final_text=self.final_text,
            usage_aggregate=self.usage_aggregate,
            stream_id=self.stream_id,
            iteration_index=iteration_index,
            total_tool_calls=total_tool_calls,
            terminal_outcome=self.terminal_outcome,
        )

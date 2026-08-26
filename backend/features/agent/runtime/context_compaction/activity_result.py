"""SoAI - Auto-compaction activity result builders [backend/features/agent/runtime/context_compaction/activity_result.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.tool_calls.context_compaction_result import (
    build_context_compaction_result_payload,
)

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict
    from features.agent.session.compaction_budget import ResolvedCompactionBudget

__all__ = (
    "AutoCompactionActivityMetadata",
    "PreparedAutoCompactionSnapshot",
    "build_auto_compaction_output_text",
    "build_auto_compaction_result_payload",
)


@dataclass(frozen=True, slots=True)
class AutoCompactionActivityMetadata:
    model: str
    compaction_budget: ResolvedCompactionBudget
    prompt_tokens_before: int
    prompt_tokens_after: int
    dropped_message_count: int
    tool_stub_count: int
    truncated_message_count: int
    summary_source: Literal["llm", "deterministic"]
    boundary_state: JSONDict

    def to_payload(self) -> JSONDict:
        payload: JSONDict = {
            "trigger": "auto",
            "model": self.model,
            "context_window_tokens": int(self.compaction_budget.context_window_tokens),
            "reserved_output_tokens": int(self.compaction_budget.reserved_output_tokens),
            "trigger_margin_ratio": float(self.compaction_budget.trigger_margin_ratio),
            "post_compact_margin_ratio": float(self.compaction_budget.post_compact_margin_ratio),
            "trigger_prompt_tokens": int(self.compaction_budget.trigger_prompt_tokens),
            "target_prompt_tokens": int(self.compaction_budget.target_prompt_tokens),
            "prompt_tokens_before": int(self.prompt_tokens_before),
            "prompt_tokens_after": int(self.prompt_tokens_after),
            "dropped_message_count": int(self.dropped_message_count),
            "tool_stub_count": int(self.tool_stub_count),
            "truncated_message_count": int(self.truncated_message_count),
            "summary_source": str(self.summary_source),
        }
        payload.update(self.boundary_state)
        return payload


@dataclass(frozen=True, slots=True)
class PreparedAutoCompactionSnapshot:
    compacted_messages: list[JSONDict]
    output_text: str
    prompt_message: JSONDict | None
    metadata: AutoCompactionActivityMetadata
    prompt_occupancy: PromptOccupancy


def build_auto_compaction_output_text(
    *,
    dropped_message_count: int,
    tool_stub_count: int,
    truncated_message_count: int,
    summary_source: Literal["llm", "deterministic"],
    summary_text: str | None,
) -> str:
    summary_line = (
        "Context compacted "
        f"(dropped={int(dropped_message_count)}, tool_stubs={int(tool_stub_count)}, "
        f"truncated={int(truncated_message_count)}, summary_source={summary_source!s})."
    )
    if summary_text is not None and summary_text.strip():
        return f"{summary_line}\n\n{summary_text}"
    return summary_line


def build_auto_compaction_result_payload(
    *,
    status: str,
    output_text: str,
    prompt_message: JSONDict | None,
    error_message: str | None,
    metadata: AutoCompactionActivityMetadata | None,
) -> JSONDict:
    return build_context_compaction_result_payload(
        status=status,
        output_text=output_text,
        prompt_message=prompt_message,
        error_message=error_message,
        compaction_details=metadata.to_payload() if metadata is not None else None,
        default_error_message="Context compaction failed.",
    )

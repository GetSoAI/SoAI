"""SoAI - Context compaction outcome models [backend/features/agent/runtime/context_compaction/outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict

__all__ = (
    "COMPACTION_SUMMARY_SOURCE_DETERMINISTIC",
    "COMPACTION_SUMMARY_SOURCE_LLM",
    "DeterministicReductionOutcome",
    "MessageHistoryCompactionOutcome",
)

COMPACTION_SUMMARY_SOURCE_LLM: Literal["llm"] = "llm"
COMPACTION_SUMMARY_SOURCE_DETERMINISTIC: Literal["deterministic"] = "deterministic"


@dataclass(frozen=True, slots=True)
class DeterministicReductionOutcome:
    compacted_messages: list[JSONDict]
    protected_floor_reached: bool


@dataclass(frozen=True, slots=True)
class MessageHistoryCompactionOutcome:
    compacted_messages: list[JSONDict]
    summary_source: Literal["llm", "deterministic"]
    prompt_occupancy: PromptOccupancy

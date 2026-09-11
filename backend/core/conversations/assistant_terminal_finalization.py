"""SoAI - Terminal assistant message finalization outcome [backend/core/conversations/assistant_terminal_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("TerminalAssistantMessageFinalization",)


@dataclass(frozen=True, slots=True)
class TerminalAssistantMessageFinalization:
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    usage_source: str | None
    generation_latency_ms: int | None
    thinking_tail_duration_ms: int | None
    terminal_reason: str | None
    terminal_code: str

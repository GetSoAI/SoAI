"""SoAI - Subagent parent tool call text stream blocks [backend/features/agent/subagents/parent_tool_call_text_blocks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from features.agent.subagents.parent_tool_call_update_models import TextBlockState

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("SubagentTextBlockBuffer",)


@dataclass(slots=True)
class SubagentTextBlockBuffer:
    closed_blocks: list[TextBlockState] = field(default_factory=list[TextBlockState])
    current_text: str = ""
    current_start_ms: int | None = None
    next_block_index: int = 0

    def add_delta(self, text: str, started_at_ms: int) -> None:
        if not text:
            return
        if self.current_start_ms is None:
            self.current_start_ms = started_at_ms
        self.current_text += text

    def close_current(self, stream_order: int) -> int:
        if not self.current_text or self.current_start_ms is None:
            return stream_order
        self.closed_blocks.append(
            TextBlockState(
                text=self.current_text,
                started_at_ms=self.current_start_ms,
                block_index=self.next_block_index,
                stream_order=stream_order,
            ),
        )
        self.next_block_index += 1
        self.current_text = ""
        self.current_start_ms = None
        return stream_order + 1

    def get_all(self, stream_order: int) -> list[TextBlockState]:
        blocks = list(self.closed_blocks)
        if self.current_text and self.current_start_ms is not None:
            blocks.append(
                TextBlockState(
                    text=self.current_text,
                    started_at_ms=self.current_start_ms,
                    block_index=self.next_block_index,
                    stream_order=stream_order,
                ),
            )
        return blocks

    def ensure_terminal_from_subagent_record(
        self,
        subagent_record: JSONDict,
        stream_order: int,
    ) -> int:
        if self.closed_blocks or self.current_text:
            return stream_order
        result_text = subagent_record.get("result_text")
        if not isinstance(result_text, str) or not result_text.strip():
            return stream_order
        started_at_ms = self._resolve_terminal_text_started_at_ms(subagent_record)
        if started_at_ms is None:
            return stream_order
        self.closed_blocks.append(
            TextBlockState(
                text=result_text,
                started_at_ms=started_at_ms,
                block_index=self.next_block_index,
                stream_order=stream_order,
            ),
        )
        self.next_block_index += 1
        return stream_order + 1

    def _resolve_terminal_text_started_at_ms(self, subagent_record: JSONDict) -> int | None:
        for field_name in ("finished_at_ms", "updated_at_ms", "started_at_ms"):
            value = subagent_record.get(field_name)
            if is_strict_int(value) and value >= 0:
                return value
        return None

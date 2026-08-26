"""SoAI - Subagent parent tool-call streaming lifecycle [backend/features/agent/subagents/parent_tool_call_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.tool_calls.deferred_tool_call_streamer import (
    DeferredToolCallDependencies,
    DeferredToolCallStreamer,
)
from features.agent.subagents.parent_tool_call_persistence import (
    build_terminal_tool_result,
    resolve_parent_tool_call_error_message,
    resolve_parent_tool_call_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("SubagentParentToolCallStreamer",)

SUBAGENT_PARENT_TOOL_NAME = "subagent_spawn"


@dataclass(slots=True)
class SubagentParentToolCallStreamer:
    deps: DeferredToolCallDependencies
    _streamer: DeferredToolCallStreamer | None = None

    def _core_streamer(self) -> DeferredToolCallStreamer:
        if self._streamer is None:
            self._streamer = DeferredToolCallStreamer(
                deps=self.deps,
            )
        return self._streamer

    async def ensure_started(self) -> None:
        await self._core_streamer().ensure_started()

    async def finalize(
        self,
        *,
        subagent_status: str,
        duration_ms: int,
        error_message: str | None,
        token_usage: JSONDict | None,
        result_payload: JSONDict | None,
    ) -> None:
        status = resolve_parent_tool_call_status(subagent_status)
        resolved_error_message = resolve_parent_tool_call_error_message(
            parent_status=status,
            subagent_status=subagent_status,
            error_message=error_message,
        )
        terminal_result = build_terminal_tool_result(
            result_payload=result_payload,
            token_usage=token_usage,
        )
        await self._core_streamer().finalize(
            status=status,
            duration_ms=max(0, int(duration_ms)),
            error_message=resolved_error_message,
            result_payload=terminal_result,
        )

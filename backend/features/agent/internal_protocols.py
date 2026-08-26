"""SoAI - Agent subsystem internal protocols [backend/features/agent/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.types.json import JSONDict

    type AgentToolCallsDetectedCallback = Callable[
        [tuple[JSONDict, ...]],
        Awaitable[None] | None,
    ]

__all__ = (
    "AgentStreamingInferenceOutcome",
    "AgentStreamingInferenceRunnerProtocol",
)


@dataclass(frozen=True, slots=True)
class AgentStreamingInferenceOutcome:
    payload: JSONDict | None
    stream_successful: bool
    done_sent: bool
    stream_id: str | None
    usage: JSONDict | None
    tool_calls: list[JSONDict]
    visible_text_chars: int
    thinking_text_chars: int
    content_index_base: int
    thinking_index_base: int
    error_message: str | None = None
    error_type: str | None = None
    transcript: OpenAIStreamTranscript | None = None


class AgentStreamingInferenceRunnerProtocol(Protocol):
    def reserve_tool_sequence_indexes(self, count: int) -> None: ...

    def commit_latest_iteration(
        self,
        *,
        visible_text_chars: int,
        thinking_text_chars: int,
        tool_calls: list[JSONDict],
    ) -> None: ...

    def discard_latest_iteration(self) -> None: ...

    async def __call__(
        self,
        payload: JSONDict,
        *,
        iteration_index: int,
        cancellation_id: str,
        on_bytes: Callable[[bytes], Awaitable[None] | None],
        on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None = None,
        on_tool_calls_detected: AgentToolCallsDetectedCallback | None = None,
    ) -> AgentStreamingInferenceOutcome: ...

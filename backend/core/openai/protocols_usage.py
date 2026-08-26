"""SoAI - OpenAI usage protocols [backend/core/openai/protocols_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("CompletionTokenTranscriptProtocol",)


class CompletionTokenTranscriptProtocol(Protocol):
    def get_reported_usage(self) -> JSONDict | None: ...

    def get_visible_text(self) -> str: ...

    def get_thinking_text(self) -> str: ...

    def get_tool_calls(self) -> list[JSONDict]: ...

    def drain_completion_token_fragments(self) -> tuple[str, ...]: ...

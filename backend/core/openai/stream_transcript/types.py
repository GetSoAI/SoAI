"""SoAI - OpenAI stream transcript shared types [backend/core/openai/stream_transcript/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("StreamTextSegment", "StreamTextSegmentLocation")


@dataclass(frozen=True, slots=True)
class StreamTextSegment:
    channel: Literal["visible", "thinking"]
    text: str


@dataclass(frozen=True, slots=True)
class StreamTextSegmentLocation:
    segment: StreamTextSegment
    container: JSONDict | list[JSONValue] | None
    key: str | int | None

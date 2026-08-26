"""SoAI - OpenAI stream transcript shared types [backend/core/openai/stream_transcript/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ("StreamTextSegment",)


@dataclass(frozen=True, slots=True)
class StreamTextSegment:
    channel: Literal["visible", "thinking"]
    text: str

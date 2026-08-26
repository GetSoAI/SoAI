"""SoAI - Token counter limits and result types [backend/core/openai/token_counter_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "APPROXIMATE_CHARS_PER_TOKEN_FLOOR",
    "APPROXIMATE_TOKEN_ENCODING_NAME",
    "PromptTokenCountResult",
    "PromptTokenCountState",
)

APPROXIMATE_TOKEN_ENCODING_NAME = "cl100k_base"
APPROXIMATE_CHARS_PER_TOKEN_FLOOR = 3.5
MESSAGE_OVERHEAD_TOKENS = 3
MESSAGE_NAME_OVERHEAD_TOKENS = 1
REPLY_PRIMING_TOKENS = 3
DEFAULT_MAX_FIELD_CHARACTERS = 268_435_456
DEFAULT_MAX_TOTAL_CHARACTERS = 268_435_456
DEFAULT_MAX_COUNTED_TOKENS = 10_000_000
TERMINAL_CAP_REASONS = frozenset({"total_character_limit", "token_limit"})


@dataclass(frozen=True, slots=True)
class PromptTokenCountResult:
    prompt_tokens: int | None
    capped: bool
    reason: str | None
    counted_characters: int = 0
    is_approximate: bool = False


@dataclass(slots=True)
class PromptTokenCountState:
    total_tokens: int = 0
    counted_characters: int = 0
    capped: bool = False
    reason: str | None = None

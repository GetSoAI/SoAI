"""SoAI - Core OpenAI protocol contracts [backend/core/openai/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = ("PromptTokenCountStateProtocol",)


class PromptTokenCountStateProtocol(Protocol):
    total_tokens: int
    counted_characters: int
    capped: bool
    reason: str | None

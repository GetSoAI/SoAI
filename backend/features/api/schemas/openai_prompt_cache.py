"""SoAI - OpenAI prompt cache schemas [backend/features/api/schemas/openai_prompt_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = (
    "PromptCacheBreakpoint",
    "PromptCacheOptions",
)


class PromptCacheBreakpoint(SoAIV1StrictModel):
    mode: Literal["explicit"]


class PromptCacheOptions(SoAIV1StrictModel):
    mode: Literal["implicit", "explicit"] | None = None
    ttl: Literal["30m"] | None = None

"""SoAI - OpenAI shared strict schema primitives [backend/features/api/schemas/openai_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from pydantic import StrictBool

from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = (
    "BaseInferenceRequest",
    "StreamOptions",
)


class BaseInferenceRequest(SoAIV1StrictModel):
    model: str


class StreamOptions(SoAIV1StrictModel):
    include_usage: StrictBool | None = None
    include_obfuscation: StrictBool | None = None

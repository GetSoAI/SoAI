"""SoAI - MCP generate image internal data types [backend/mcp/tools/generate_image_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass

__all__ = ("ImageGenerationDeadline", "ImageGenerationRequest", "ImageGenerationResult")


@dataclass(frozen=True, slots=True)
class ImageGenerationDeadline:
    monotonic: float

    def remaining(self) -> float:
        return max(0.0, self.monotonic - time.monotonic())

    def request_timeout(self) -> float:
        return max(0.1, min(30.0, self.remaining()))


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    cfg_scale: float
    seed: int | None


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    provider: str
    image_bytes: bytes
    width: int
    height: int
    seed: int | None

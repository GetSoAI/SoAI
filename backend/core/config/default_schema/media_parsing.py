"""SoAI - Default config schema: media parsing [backend/core/config/default_schema/media_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_media_parsing_defaults",)


def build_media_parsing_defaults() -> ConfigDict:
    return {
        "MEDIA_PARSING": {
            "VIDEO_OCR_FRAMES_PER_SECOND": 1.0,
            "VIDEO_OCR_MAX_FRAMES": 360,
            "VIDEO_OCR_MAX_TEXT_CHARS": 250_000,
            "OCR_FRAME_TIMEOUT_SEC": 60,
            "PARSE_TIMEOUT_SEC": 21_600,
        },
    }

"""SoAI - Provider video projection settings [backend/features/api/runtime/webui_attachments/provider_video_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric_lenient import (
    coerce_lenient_positive_int,
    coerce_positive_timeout_seconds,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = ("ProviderVideoSettings", "read_provider_video_settings")

_PREFIX = "SERVER.WEBUI.PROVIDER_VIDEO"


@dataclass(frozen=True, slots=True)
class ProviderVideoSettings:
    max_frames_per_request: int
    max_encoded_chars_per_request: int
    projection_timeout_sec: float
    max_concurrent_projections: int

    @property
    def signature(self) -> str:
        return (
            f"{self.max_frames_per_request}:"
            f"{self.max_encoded_chars_per_request}:"
            f"{self.projection_timeout_sec:.6f}"
        )


def read_provider_video_settings(config: ConfigProtocol) -> ProviderVideoSettings:
    return ProviderVideoSettings(
        max_frames_per_request=coerce_lenient_positive_int(
            config.get(f"{_PREFIX}.MAX_FRAMES_PER_REQUEST"),
            default=12,
            minimum=1,
            maximum=10_000,
        ),
        max_encoded_chars_per_request=coerce_lenient_positive_int(
            config.get(f"{_PREFIX}.MAX_ENCODED_CHARS_PER_REQUEST"),
            default=16_777_216,
            minimum=1,
        ),
        projection_timeout_sec=coerce_positive_timeout_seconds(
            config.get(f"{_PREFIX}.PROJECTION_TIMEOUT_SEC"),
            default=120.0,
        ),
        max_concurrent_projections=coerce_lenient_positive_int(
            config.get(f"{_PREFIX}.MAX_CONCURRENT_PROJECTIONS"),
            default=2,
            minimum=1,
            maximum=64,
        ),
    )

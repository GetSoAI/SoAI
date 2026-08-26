"""SoAI - Modality usage metric records [backend/core/metrics/usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from core.errors.exceptions import ValidationError
from core.validation.integers import is_non_negative_strict_int

__all__ = (
    "MODALITY_USAGE_FIELDS",
    "USAGE_METADATA_AUDIO_INPUT_BYTES",
    "ModalityUsageRecord",
    "create_modality_usage_counts",
)

USAGE_METADATA_AUDIO_INPUT_BYTES: Final[str] = "audio_input_bytes"

MODALITY_USAGE_FIELDS: Final[tuple[str, ...]] = (
    "text_tokens",
    USAGE_METADATA_AUDIO_INPUT_BYTES,
    "audio_input_seconds",
    "audio_output_bytes",
    "audio_output_seconds",
    "image_input_count",
    "image_output_count",
)


@dataclass(frozen=True, slots=True)
class ModalityUsageRecord:
    plugin: str
    model_id: str
    client_id: str
    text_tokens: int = 0
    audio_input_bytes: int = 0
    audio_input_seconds: float = 0.0
    audio_output_bytes: int = 0
    audio_output_seconds: float = 0.0
    image_input_count: int = 0
    image_output_count: int = 0

    def __post_init__(self) -> None:
        _require_non_empty_text(self.plugin, "plugin")
        _require_non_empty_text(self.model_id, "model_id")
        _require_non_empty_text(self.client_id, "client_id")
        _require_non_negative_int(self.text_tokens, "text_tokens")
        _require_non_negative_int(self.audio_input_bytes, USAGE_METADATA_AUDIO_INPUT_BYTES)
        _require_non_negative_float(self.audio_input_seconds, "audio_input_seconds")
        _require_non_negative_int(self.audio_output_bytes, "audio_output_bytes")
        _require_non_negative_float(self.audio_output_seconds, "audio_output_seconds")
        _require_non_negative_int(self.image_input_count, "image_input_count")
        _require_non_negative_int(self.image_output_count, "image_output_count")

    def has_usage(self) -> bool:
        return (
            self.text_tokens > 0
            or self.audio_input_bytes > 0
            or self.audio_input_seconds > 0.0
            or self.audio_output_bytes > 0
            or self.audio_output_seconds > 0.0
            or self.image_input_count > 0
            or self.image_output_count > 0
        )


def create_modality_usage_counts() -> dict[str, int | float]:
    return {
        "text_tokens": 0,
        USAGE_METADATA_AUDIO_INPUT_BYTES: 0,
        "audio_input_seconds": 0.0,
        "audio_output_bytes": 0,
        "audio_output_seconds": 0.0,
        "image_input_count": 0,
        "image_output_count": 0,
    }


def _require_non_empty_text(value: str, field: str) -> None:
    if not value.strip():
        raise ValidationError(f"{field} must be a non-empty string.")


def _require_non_negative_int(value: int, field: str) -> None:
    if not is_non_negative_strict_int(value):
        raise ValidationError(f"{field} must be a non-negative integer.")


def _require_non_negative_float(value: float, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(f"{field} must be a non-negative finite number.")
    resolved_value = float(value)
    if not math.isfinite(resolved_value) or resolved_value < 0.0:
        raise ValidationError(f"{field} must be a non-negative finite number.")

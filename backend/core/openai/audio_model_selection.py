"""SoAI - Shared OpenAI audio model selector predicates [backend/core/openai/audio_model_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.model_info_fields import is_model_info_active_and_enabled
from core.openai.capability_checks import is_openai_model_capability_enabled

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "is_auto_audio_model_selector",
    "model_supports_openai_audio_endpoint",
)


def is_auto_audio_model_selector(requested_model: str) -> bool:
    return requested_model.strip().lower() == "auto"


def model_supports_openai_audio_endpoint(
    model_entry: JSONDict,
    endpoint_capability: str,
) -> bool:
    if not is_model_info_active_and_enabled(model_entry):
        return False
    return is_openai_model_capability_enabled(
        model_entry,
        category="endpoints",
        token=endpoint_capability,
    )

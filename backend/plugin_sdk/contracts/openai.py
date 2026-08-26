"""SoAI - Plugin SDK OpenAI compatibility enums and helpers [backend/plugin_sdk/contracts/openai.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.capability_taxonomy import (
    OPENAI_CAPABILITY_CATEGORIES,
    OPENAI_FEATURE_MATRIX,
    OpenAIChatFeature,
    OpenAIEndpoint,
    OpenAIImageFeature,
    OpenAIModality,
)
from core.openai.compatibility import (
    ExternalProviderMode,
    normalize_external_provider_mode,
    normalize_openai_modalities,
    normalize_openai_modalities_strict,
    normalize_openai_modality,
)

__all__ = (
    "OPENAI_CAPABILITY_CATEGORIES",
    "OPENAI_FEATURE_MATRIX",
    "ExternalProviderMode",
    "OpenAIChatFeature",
    "OpenAIEndpoint",
    "OpenAIImageFeature",
    "OpenAIModality",
    "normalize_external_provider_mode",
    "normalize_openai_modalities",
    "normalize_openai_modalities_strict",
    "normalize_openai_modality",
)

"""SoAI - OpenAI-related plugin SDK export policy data [backend/core/plugins/sdk_public_openai_exports.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "OPENAI_AUDIO_UPLOAD_RESPONSE_EXPORTS",
    "OPENAI_EXPORTS",
    "OPENAI_PROVIDER_TRANSPORT_EXPORTS",
)

OPENAI_EXPORTS: tuple[str, ...] = (
    "normalize_openai_modality",
    "normalize_openai_modalities_strict",
    "normalize_openai_modalities",
    "normalize_external_provider_mode",
    "OpenAIModality",
    "OpenAIImageFeature",
    "OpenAIEndpoint",
    "OpenAIChatFeature",
    "OPENAI_FEATURE_MATRIX",
    "OPENAI_CAPABILITY_CATEGORIES",
    "ExternalProviderMode",
)
OPENAI_AUDIO_UPLOAD_RESPONSE_EXPORTS: tuple[str, ...] = (
    "read_audio_upload_error_response",
    "is_audio_upload_error_response",
    "build_audio_upload_error_response",
    "AUDIO_UPLOAD_ERROR_RESPONSE_MARKER",
)
OPENAI_PROVIDER_TRANSPORT_EXPORTS: tuple[str, ...] = (
    "normalize_openai_provider_query_params",
    "compose_openai_provider_url",
    "build_openai_upstream_error_details",
    "build_openai_provider_headers",
)

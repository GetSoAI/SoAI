"""SoAI - OpenAI text-to-speech media type resolution [backend/core/openai/tts_media_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("resolve_tts_response_media_type",)


def resolve_tts_response_media_type(response_format: str) -> str:
    normalized = response_format.strip().lower()
    if normalized == "opus":
        return "audio/opus"
    if normalized == "aac":
        return "audio/aac"
    if normalized == "flac":
        return "audio/flac"
    if normalized == "wav":
        return "audio/wav"
    if normalized == "pcm":
        return "application/octet-stream"
    return "audio/mpeg"

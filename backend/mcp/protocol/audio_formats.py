"""SoAI - MCP audio MIME type conversions [backend/mcp/protocol/audio_formats.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.files.content_types import normalize_content_type

__all__ = ("resolve_openai_audio_format",)


def resolve_openai_audio_format(mime_type: str) -> str | None:
    normalized = normalize_content_type(mime_type)
    match normalized:
        case "audio/wav" | "audio/x-wav" | "audio/wave":
            return "wav"
        case "audio/mpeg" | "audio/mp3":
            return "mp3"
        case "audio/webm":
            return "webm"
        case "audio/ogg":
            return "ogg"
        case _:
            return None

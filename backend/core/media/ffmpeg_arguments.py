"""SoAI - Shared FFmpeg extraction arguments [backend/core/media/ffmpeg_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.media.process_runtime import media_process_base_argv

__all__ = ("build_ffmpeg_extraction_prefix",)


def build_ffmpeg_extraction_prefix(
    source_path: str,
    timestamp_seconds: float,
) -> tuple[str, ...]:
    return (
        *media_process_base_argv(),
        "-ss",
        f"{timestamp_seconds:.6f}",
        "-i",
        source_path,
    )

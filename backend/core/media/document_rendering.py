"""SoAI - Deterministic searchable media document rendering [backend/core/media/document_rendering.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.media.types import (
    AudioProbeResult,
    TranscriptionResult,
    TranscriptSegment,
    VideoProbeResult,
    VisibleTextOccurrence,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("render_audio_document", "render_video_document")


def _timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000.0))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, remaining_milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{remaining_milliseconds:03d}"


def _transcript_lines(segments: tuple[TranscriptSegment, ...]) -> list[str]:
    if not segments:
        return ["No speech detected."]
    return [
        f"[{_timestamp(segment.start_seconds)} - {_timestamp(segment.end_seconds)}] {segment.text}"
        for segment in segments
    ]


def _visible_text_lines(occurrences: tuple[VisibleTextOccurrence, ...]) -> list[str]:
    if not occurrences:
        return ["No visible text detected."]
    return [
        f"[{_timestamp(occurrence.start_seconds)} - {_timestamp(occurrence.end_seconds)}] {occurrence.text}"
        for occurrence in occurrences
    ]


def render_audio_document(
    probe: AudioProbeResult,
    transcription: TranscriptionResult,
    *,
    tags: JSONDict | None = None,
    transcription_note: str | None = None,
) -> str:
    metadata = [
        "Media type: audio",
        f"Duration: {_timestamp(probe.duration_seconds)}",
        f"Container: {probe.container}",
        f"Audio codec: {probe.audio_codec}",
    ]
    if transcription.language is not None:
        metadata.append(f"Language: {transcription.language}")
    for key, label in (
        ("title", "Title"),
        ("artist", "Artist"),
        ("album", "Album"),
        ("genre", "Genre"),
        ("year", "Year"),
    ):
        value = tags.get(key) if tags is not None else None
        if isinstance(value, str) and value:
            metadata.append(f"{label}: {value}")
    transcript_lines = (
        [transcription_note]
        if transcription_note is not None
        else _transcript_lines(transcription.segments)
    )
    return "\n".join((*metadata, "", "Transcript:", *transcript_lines))


def render_video_document(
    probe: VideoProbeResult,
    transcription: TranscriptionResult,
    visible_text: tuple[VisibleTextOccurrence, ...],
    *,
    extraction_note: str | None,
) -> str:
    metadata = [
        "Media type: video",
        f"Duration: {_timestamp(probe.duration_seconds)}",
        f"Dimensions: {probe.width}x{probe.height}",
        f"Container: {probe.container}",
        f"Video codec: {probe.video_codec}",
        f"Audio: {'present' if probe.audio_present else 'not present'}",
    ]
    if probe.audio_codec is not None:
        metadata.append(f"Audio codec: {probe.audio_codec}")
    if transcription.language is not None:
        metadata.append(f"Language: {transcription.language}")
    sections = [
        *metadata,
        "",
        "Speech:",
        *_transcript_lines(transcription.segments),
        "",
        "Visible text:",
        *_visible_text_lines(visible_text),
    ]
    if extraction_note is not None:
        sections.extend(("", f"Extraction note: {extraction_note}"))
    return "\n".join(sections)

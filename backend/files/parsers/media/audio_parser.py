"""SoAI - Asynchronous searchable audio parser [backend/files/parsers/media/audio_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from tinytag import TinyTag, TinyTagException

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.files.extraction_state import ExtractionState
from core.files.parse_execution import raise_if_parse_cancelled, report_parse_progress
from core.files.protocols import FileParserProtocol
from core.files.types import ParsedDocument, ParseExecutionContext
from core.media.cancellation import await_media_operation
from core.media.config import resolve_media_parsing_config
from core.media.document_rendering import render_audio_document
from core.media.probing import probe_audio
from core.media.transcription_request import request_media_transcription
from core.media.types import TranscriptionResult
from core.types.json import JSONDict

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.media.protocols import MediaTranscriptionRuntimeProtocol

__all__ = ("AudioParser", "AudioParserDependencies")


@dataclass(frozen=True, slots=True)
class AudioParserDependencies:
    transcription_runtime: MediaTranscriptionRuntimeProtocol
    config: ConfigProtocol
    transcription_available: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AudioParserDependencies",
            transcription_runtime=self.transcription_runtime,
            config=self.config,
            transcription_available=self.transcription_available,
        )


class AudioParser(FileParserProtocol):
    content_separator = "\n\n"

    def __init__(self, deps: AudioParserDependencies) -> None:
        self._transcription_runtime = deps.transcription_runtime
        self._config = deps.config
        self._transcription_available = deps.transcription_available

    @override
    async def parse(self, context: ParseExecutionContext) -> ParsedDocument:
        config = resolve_media_parsing_config(self._config)
        raise_if_parse_cancelled(context)
        await report_parse_progress(context, 0.02, "probing_audio")
        probe = await await_media_operation(
            probe_audio(
                context.source_path,
                timeout_seconds=min(context.remaining_seconds(), config.probe_timeout_sec),
            ),
            context.cancellation_token,
            extraction_deadline=context.extraction_deadline,
        )
        raise_if_parse_cancelled(context)
        tags = await _read_tags(context.source_path)
        await report_parse_progress(context, 0.1, "transcribing_audio")

        async def transcription_progress(value: float, stage: str) -> None:
            await report_parse_progress(context, 0.1 + value * 0.9, stage)

        transcription_note = None
        if self._transcription_available:
            transcription = await request_media_transcription(
                self._transcription_runtime,
                context=context,
                duration_seconds=probe.duration_seconds,
                model_name=config.whisper_model,
                progress_callback=transcription_progress,
            )
        else:
            transcription = TranscriptionResult(text="", language=None, segments=())
            transcription_note = "Speech transcription is unavailable on this platform."
        raise_if_parse_cancelled(context)
        file_size = await run_joined_thread_call(
            os.path.getsize,
            context.source_path,
            task_name="audio-source-size",
        )
        metadata: JSONDict = {
            "file_size": file_size,
            "duration_seconds": probe.duration_seconds,
            "container": probe.container,
            "audio_codec": probe.audio_codec,
        }
        if probe.sample_rate_hz is not None:
            metadata["sample_rate_hz"] = probe.sample_rate_hz
        if probe.channels is not None:
            metadata["channels"] = probe.channels
        if probe.bit_rate is not None:
            metadata["bit_rate"] = probe.bit_rate
        if transcription.language is not None:
            metadata["language"] = transcription.language
        metadata.update(tags)
        warnings = (transcription_note,) if transcription_note is not None else ()
        return ParsedDocument(
            content=render_audio_document(
                probe,
                transcription,
                tags=tags,
                transcription_note=transcription_note,
            ),
            metadata=metadata,
            extraction_state=(
                ExtractionState.DEGRADED
                if transcription_note is not None
                else ExtractionState.COMPLETE
            ),
            warnings=warnings,
        )


async def _read_tags(source_path: str) -> JSONDict:
    return await asyncio.to_thread(_read_optional_tags, source_path)


def _read_optional_tags(source_path: str) -> JSONDict:
    try:
        tag = TinyTag.get(source_path, image=False)
    except (TinyTagException, OSError):
        return {}
    metadata: JSONDict = {}
    for key, value in (
        ("title", tag.title),
        ("artist", tag.artist),
        ("album", tag.album),
        ("genre", tag.genre),
        ("year", tag.year),
    ):
        rendered = str(value).strip() if value is not None else ""
        if rendered:
            metadata[key] = rendered
    return metadata

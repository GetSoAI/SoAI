"""SoAI - Asynchronous searchable video parser [backend/files/parsers/media/video_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exceptions import ProcessError, ServiceUnavailableError, SoAITimeoutError
from core.files.extraction_state import ExtractionState
from core.files.parse_execution import raise_if_parse_cancelled, report_parse_progress
from core.files.protocols import FileParserProtocol
from core.files.types import ParsedDocument, ParseExecutionContext
from core.media.cancellation import await_media_operation
from core.media.config import resolve_media_parsing_config
from core.media.document_rendering import render_video_document
from core.media.probing import probe_video
from core.media.transcription_request import request_media_transcription
from core.media.types import TranscriptionResult
from core.media.video_text import apply_visible_text_budget, merge_adjacent_visible_text
from core.runtime.network_policy import OfflineModeError
from core.types.json import JSONDict
from files.parsers.media.video_frame_ocr import read_video_ocr_frames

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.media.config import MediaParsingConfig
    from core.media.protocols import MediaOcrRuntimeProtocol, MediaTranscriptionRuntimeProtocol
    from core.media.types import VideoProbeResult

__all__ = ("VideoParser", "VideoParserDependencies")

_TRANSCRIPTION_WARNING = "Speech transcription was unavailable."
_OCR_WARNING = "Visible text extraction was incomplete."
_BUDGET_WARNING = "Visible text was bounded across the complete video timeline."


@dataclass(frozen=True, slots=True)
class VideoParserDependencies:
    transcription_runtime: MediaTranscriptionRuntimeProtocol
    ocr_runtime: MediaOcrRuntimeProtocol
    config: ConfigProtocol
    storage_manager: StorageManagerProtocol
    transcription_available: bool

    def __post_init__(self) -> None:
        require_dependencies(
            owner="VideoParserDependencies",
            transcription_runtime=self.transcription_runtime,
            ocr_runtime=self.ocr_runtime,
            config=self.config,
            storage_manager=self.storage_manager,
            transcription_available=self.transcription_available,
        )


class VideoParser(FileParserProtocol):
    content_separator = "\n\n"

    def __init__(self, deps: VideoParserDependencies) -> None:
        self._transcription_runtime = deps.transcription_runtime
        self._ocr_runtime = deps.ocr_runtime
        self._config = deps.config
        self._storage_manager = deps.storage_manager
        self._transcription_available = deps.transcription_available

    @override
    async def parse(self, context: ParseExecutionContext) -> ParsedDocument:
        config = resolve_media_parsing_config(self._config)
        raise_if_parse_cancelled(context)
        await report_parse_progress(context, 0.01, "probing_video")
        probe = await await_media_operation(
            probe_video(
                context.source_path,
                timeout_seconds=min(context.remaining_seconds(), config.probe_timeout_sec),
            ),
            context.cancellation_token,
            extraction_deadline=context.extraction_deadline,
        )
        transcription, transcription_warning = await self._transcribe(context, probe, config)
        frame_ocr = await read_video_ocr_frames(
            context=context,
            probe=probe,
            media_config=config,
            config=self._config,
            storage_manager=self._storage_manager,
            ocr_runtime=self._ocr_runtime,
        )
        ocr_warning = _OCR_WARNING if frame_ocr.incomplete else None
        occurrences = merge_adjacent_visible_text(frame_ocr.frames)
        budget = apply_visible_text_budget(
            occurrences,
            maximum_text_chars=config.video_ocr_max_text_chars,
        )
        warnings = tuple(
            warning
            for warning in (
                transcription_warning,
                ocr_warning,
                _BUDGET_WARNING if budget.truncated else None,
            )
            if warning is not None
        )
        successful_transcription = probe.audio_present and transcription_warning is None
        successful_ocr = bool(frame_ocr.frames)
        if not successful_transcription and not successful_ocr:
            raise ProcessError("Video speech and visible text extraction failed.")
        extraction_state = ExtractionState.DEGRADED if warnings else ExtractionState.COMPLETE
        extraction_note = " ".join(warnings) if warnings else None
        file_size = await run_joined_thread_call(
            os.path.getsize,
            context.source_path,
            task_name="video-source-size",
        )
        metadata: JSONDict = {
            "file_size": file_size,
            "duration_seconds": probe.duration_seconds,
            "width": probe.width,
            "height": probe.height,
            "container": probe.container,
            "video_codec": probe.video_codec,
            "audio_present": probe.audio_present,
            "ocr_text_truncated": budget.truncated,
            "ocr_original_text_chars": budget.original_text_chars,
            "ocr_retained_text_chars": budget.retained_text_chars,
        }
        if probe.audio_codec is not None:
            metadata["audio_codec"] = probe.audio_codec
        if probe.frame_rate is not None:
            metadata["frame_rate"] = probe.frame_rate
        await report_parse_progress(context, 1.0, "media_parsing_complete")
        return ParsedDocument(
            content=render_video_document(
                probe,
                transcription,
                budget.occurrences,
                extraction_note=extraction_note,
            ),
            metadata=metadata,
            extraction_state=extraction_state,
            warnings=warnings,
        )

    async def _transcribe(
        self,
        context: ParseExecutionContext,
        probe: VideoProbeResult,
        config: MediaParsingConfig,
    ) -> tuple[TranscriptionResult, str | None]:
        if not probe.audio_present:
            return TranscriptionResult(text="", language=None, segments=()), None
        if not self._transcription_available:
            return (
                TranscriptionResult(text="", language=None, segments=()),
                _TRANSCRIPTION_WARNING,
            )

        async def transcription_progress(value: float, stage: str) -> None:
            await report_parse_progress(context, 0.05 + value * 0.4, stage)

        try:
            result = await request_media_transcription(
                self._transcription_runtime,
                context=context,
                duration_seconds=probe.duration_seconds,
                model_name=config.whisper_model,
                progress_callback=transcription_progress,
            )
            return result, None
        except (
            OfflineModeError,
            ProcessError,
            ServiceUnavailableError,
            SoAITimeoutError,
        ):
            return (
                TranscriptionResult(text="", language=None, segments=()),
                _TRANSCRIPTION_WARNING,
            )

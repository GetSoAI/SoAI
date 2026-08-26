"""SoAI - Application-owned chunked transcription runtime [backend/core/media/transcription_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exceptions import SoAITimeoutError, StateError
from core.files.temp_directory_scope import scoped_temp_directory
from core.files.upload_policy import resolve_temp_directory_runtime
from core.media.audio_extraction import estimate_wav_bytes, extract_audio_chunk
from core.media.job_storage import remove_media_file
from core.media.timeline import map_chunk_transcript, plan_audio_chunks
from core.media.types import TranscriptionChunkResult, TranscriptionResult, TranscriptSegment
from core.timing.constants import LONG_IDLE_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.files.types import ParseProgressCallback
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.media.protocols import TranscriptionChunkGatewayProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("TranscriptionRuntime", "TranscriptionRuntimeDependencies")


@dataclass(frozen=True, slots=True)
class TranscriptionRuntimeDependencies:
    config: ConfigProtocol
    gateway: TranscriptionChunkGatewayProtocol
    chunk_seconds: int
    audio_extraction_timeout_seconds: float
    temp_reservation_safety_multiplier: int
    storage_manager: StorageManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TranscriptionRuntimeDependencies",
            audio_extraction_timeout_seconds=self.audio_extraction_timeout_seconds,
            chunk_seconds=self.chunk_seconds,
            config=self.config,
            gateway=self.gateway,
            storage_manager=self.storage_manager,
            temp_reservation_safety_multiplier=self.temp_reservation_safety_multiplier,
        )


class TranscriptionRuntime:
    def __init__(self, deps: TranscriptionRuntimeDependencies) -> None:
        self._gateway = deps.gateway
        self._chunk_seconds = deps.chunk_seconds
        self._audio_extraction_timeout_seconds = deps.audio_extraction_timeout_seconds
        self._temp_reservation_safety_multiplier = deps.temp_reservation_safety_multiplier
        self._storage_manager = deps.storage_manager
        self._temp_root = resolve_temp_directory_runtime(deps.config)

    async def transcribe(
        self,
        *,
        source_path: str,
        duration_seconds: float,
        model_name: str,
        language: str | None,
        task: str,
        include_word_timestamps: bool,
        extraction_deadline: float,
        progress_callback: ParseProgressCallback | None = None,
    ) -> TranscriptionResult:
        chunks = plan_audio_chunks(
            duration_seconds=duration_seconds,
            chunk_seconds=self._chunk_seconds,
        )
        if not chunks:
            return TranscriptionResult(text="", language=language, segments=())
        mapped_segments: list[TranscriptSegment] = []
        mapped_segment_details: list[JSONDict] = []
        transcript_parts: list[str] = []
        detected_language = language
        async with scoped_temp_directory(
            directory=self._temp_root,
            prefix="media-transcription-",
            operation_label="media-transcription",
        ) as scratch_dir:
            for chunk_index, chunk in enumerate(chunks):
                remaining = extraction_deadline - time.monotonic()
                if remaining <= 0:
                    raise SoAITimeoutError("Media transcription deadline expired.")
                chunk_path = os.path.join(scratch_dir, f"chunk-{chunk.index:06d}.wav")
                estimate = estimate_wav_bytes(
                    chunk.end_seconds - chunk.start_seconds,
                    self._temp_reservation_safety_multiplier,
                )
                with self._storage_manager.reserve_disk_space(
                    path=chunk_path,
                    required_bytes=estimate,
                    operation="core.media.transcription.audio_chunk",
                    details={"chunk_index": chunk.index},
                ) as reservation:
                    await extract_audio_chunk(
                        source_path=source_path,
                        chunk=chunk,
                        output_path=chunk_path,
                        timeout_seconds=min(remaining, self._audio_extraction_timeout_seconds),
                    )
                    chunk_size = await run_joined_thread_call(
                        os.path.getsize,
                        chunk_path,
                        task_name="media-transcription-chunk-size",
                    )
                    with reservation.claim_write_bytes(chunk_size) as claim:
                        claim.commit()
                    remaining = extraction_deadline - time.monotonic()
                    if remaining <= 0:
                        raise SoAITimeoutError("Media transcription deadline expired.")
                    raw_result = await self._gateway.transcribe_chunk(
                        file_path=chunk_path,
                        model_name=model_name,
                        language=language,
                        task=task,
                        include_word_timestamps=include_word_timestamps,
                        timeout_seconds=min(remaining, LONG_IDLE_TIMEOUT_SEC),
                    )
                mapped = map_chunk_transcript(
                    chunk,
                    _parse_chunk_result(raw_result, chunk.end_seconds - chunk.start_seconds),
                    media_duration_seconds=duration_seconds,
                )
                if mapped.text:
                    transcript_parts.append(mapped.text)
                mapped_segments.extend(mapped.segments)
                mapped_segment_details.extend(mapped.segment_details)
                if detected_language is None and mapped.language is not None:
                    detected_language = mapped.language
                await run_joined_thread_call(
                    remove_media_file,
                    chunk_path,
                    task_name="media-transcription-chunk-remove",
                )
                if progress_callback is not None:
                    await progress_callback(
                        (chunk_index + 1) / chunks.total_chunks,
                        "transcribing_audio",
                    )
        return TranscriptionResult(
            text=" ".join(transcript_parts),
            language=detected_language,
            segments=tuple(mapped_segments),
            segment_details=tuple(mapped_segment_details),
        )

    async def shutdown(self) -> None:
        await self._gateway.shutdown()


def _number(value: JSONValue) -> float | None:
    if isinstance(value, bool):
        return None
    number = float(value) if isinstance(value, int | float) else math.nan
    return number if math.isfinite(number) else None


def _parse_chunk_result(raw: JSONDict, chunk_duration: float) -> TranscriptionChunkResult:
    text_value = raw.get("text")
    language_value = raw.get("language")
    segments_value = raw.get("segments")
    segments: list[TranscriptSegment] = []
    segment_details: list[JSONDict] = []
    if isinstance(segments_value, list):
        for value in segments_value:
            if not isinstance(value, dict):
                continue
            start = _number(value.get("start"))
            end = _number(value.get("end"))
            segment_text = value.get("text")
            if start is None or end is None or end <= start or not isinstance(segment_text, str):
                continue
            segments.append(TranscriptSegment(start, end, segment_text))
            segment_details.append(dict(value))
    normalized_text = " ".join(text_value.split()) if isinstance(text_value, str) else ""
    if normalized_text and not segments:
        segments.append(TranscriptSegment(0.0, chunk_duration, normalized_text))
        segment_details.append(
            {"start": 0.0, "end": chunk_duration, "text": normalized_text},
        )
    if not isinstance(segments_value, list):
        raise StateError("Media transcription worker returned invalid segments.")
    return TranscriptionChunkResult(
        text=normalized_text,
        language=language_value if isinstance(language_value, str) else None,
        segments=tuple(segments),
        segment_details=tuple(segment_details),
    )

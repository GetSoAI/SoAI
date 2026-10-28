"""SoAI - Application-owned chunked transcription runtime [backend/core/media/transcription_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.di.validation import require_dependencies
from core.errors.exceptions import SoAITimeoutError
from core.files.temp_directory_scope import scoped_temp_directory
from core.files.upload_policy import resolve_temp_directory_runtime
from core.media.audio_extraction import estimate_wav_bytes, extract_audio_chunk
from core.media.timeline import map_chunk_transcript, plan_audio_chunks
from core.media.transcription_contracts import SpeechChunkRequest
from core.media.types import TranscriptionResult, TranscriptSegment

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.media.protocols import TranscriptionChunkGatewayProtocol
    from core.media.speech_selection import ResolvedSpeechModel
    from core.media.speech_setup import SpeechTask
    from core.media.transcription_contracts import MediaTranscriptionRequest
    from core.types.json import JSONDict

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

    async def resolve_model(self, *, selector: str, task: SpeechTask) -> ResolvedSpeechModel:
        return await self._gateway.resolve_model(selector=selector, task=task)

    async def transcribe(self, request: MediaTranscriptionRequest) -> TranscriptionResult:
        try:
            async with asyncio.timeout_at(request.extraction_deadline):
                _require_remaining(request.extraction_deadline)
                chunks = plan_audio_chunks(
                    duration_seconds=request.duration_seconds,
                    chunk_seconds=self._chunk_seconds,
                )
                model = await self._gateway.resolve_model(
                    selector=request.selector,
                    task=request.options.task,
                )
                if not chunks:
                    return TranscriptionResult(
                        text="",
                        language=None,
                        segments=(),
                        model_id=model.universal_id,
                    )
                mapped_segments: list[TranscriptSegment] = []
                mapped_segment_details: list[JSONDict] = []
                transcript_parts: list[str] = []
                detected_language = None
                async with scoped_temp_directory(
                    directory=self._temp_root,
                    prefix="media-transcription-",
                    operation_label="media-transcription",
                ) as scratch_dir:
                    for chunk_index, chunk in enumerate(chunks):
                        remaining = _require_remaining(request.extraction_deadline)
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
                                source_path=request.source_path,
                                chunk=chunk,
                                output_path=chunk_path,
                                timeout_seconds=min(
                                    remaining, self._audio_extraction_timeout_seconds
                                ),
                            )
                            chunk_size = await run_joined_thread_call(
                                os.path.getsize,
                                chunk_path,
                                task_name="media-transcription-chunk-size",
                            )
                            with reservation.claim_write_bytes(chunk_size) as claim:
                                claim.commit()
                            _require_remaining(request.extraction_deadline)
                            chunk_result = await self._gateway.transcribe_chunk(
                                SpeechChunkRequest(
                                    file_path=chunk_path,
                                    byte_count=chunk_size,
                                    chunk_index=chunk.index,
                                    model=model,
                                    options=request.options,
                                    request_context=request.request_context,
                                    deadline_monotonic=request.extraction_deadline,
                                ),
                            )
                        mapped = map_chunk_transcript(
                            chunk,
                            chunk_result,
                            media_duration_seconds=request.duration_seconds,
                        )
                        if mapped.text:
                            transcript_parts.append(mapped.text)
                        mapped_segments.extend(mapped.segments)
                        mapped_segment_details.extend(mapped.segment_details)
                        if detected_language is None and mapped.language is not None:
                            detected_language = mapped.language
                        if request.progress_callback is not None:
                            await request.progress_callback(
                                (chunk_index + 1) / chunks.total_chunks,
                                "transcribing_audio",
                            )
                return TranscriptionResult(
                    text=" ".join(transcript_parts),
                    language=detected_language,
                    segments=tuple(mapped_segments),
                    segment_details=tuple(mapped_segment_details),
                    model_id=model.universal_id,
                )
        except TimeoutError as exception:
            raise SoAITimeoutError(
                "Media transcription deadline expired.", cause=exception
            ) from exception

    async def shutdown(self) -> None:
        await self._gateway.shutdown()


def _require_remaining(extraction_deadline: float) -> float:
    remaining = extraction_deadline - time.monotonic()
    if remaining <= 0:
        raise SoAITimeoutError("Media transcription deadline expired.")
    return remaining

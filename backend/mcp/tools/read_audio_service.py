"""SoAI - MCP read_audio contract projection from shared media runtime [backend/mcp/tools/read_audio_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.media.config import resolve_media_parsing_config
from core.media.probing import probe_audio
from mcp.tools.read_audio_analysis import build_audio_analysis
from mcp.tools.read_audio_metadata import (
    build_audio_container_metadata,
    build_audio_source_metadata,
)
from mcp.tools.read_audio_transcript import (
    build_read_audio_diagnostics,
    build_read_audio_transcript,
    require_json_dict_list,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.media.protocols import MediaTranscriptionRuntimeProtocol
    from core.types.json import JSONDict

__all__ = ("ReadAudioService", "ReadAudioServiceDependencies")


@dataclass(frozen=True, slots=True)
class ReadAudioServiceDependencies:
    config: ConfigProtocol
    transcription_runtime: MediaTranscriptionRuntimeProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ReadAudioServiceDependencies",
            config=self.config,
            transcription_runtime=self.transcription_runtime,
        )


class ReadAudioService:
    def __init__(self, deps: ReadAudioServiceDependencies) -> None:
        self._config = deps.config
        self._transcription_runtime = deps.transcription_runtime

    async def read_audio(
        self,
        *,
        file_path: str,
        model_name: str,
        language: str | None,
        task: str,
        include_word_timestamps: bool,
    ) -> JSONDict:
        config = resolve_media_parsing_config(self._config)
        deadline = time.monotonic() + config.parse_timeout_sec
        probe = await probe_audio(file_path, timeout_seconds=config.probe_timeout_sec)
        result = await self._transcription_runtime.transcribe(
            source_path=file_path,
            duration_seconds=probe.duration_seconds,
            model_name=model_name,
            language=language,
            task=task,
            include_word_timestamps=include_word_timestamps,
            extraction_deadline=deadline,
        )
        raw_result: JSONDict = {
            "text": result.text,
            "language": result.language,
            "segments": list(result.segment_details),
        }
        transcript = build_read_audio_transcript(
            raw_result,
            model_name=model_name,
            include_words=include_word_timestamps,
        )
        transcript["duration_seconds"] = probe.duration_seconds
        segments = require_json_dict_list(transcript.get("segments"))
        diagnostics = build_read_audio_diagnostics(segments)
        speech_timeline, content_stats, model_notes = build_audio_analysis(
            text=str(transcript["text"]),
            duration_seconds=probe.duration_seconds,
            segments=segments,
            diagnostics=diagnostics,
        )
        return {
            "source": build_audio_source_metadata(file_path),
            "container": build_audio_container_metadata(file_path),
            "request": {
                "model": model_name,
                "task": task,
                "requested_language": language,
                "include_word_timestamps": include_word_timestamps,
            },
            "transcript": transcript,
            "speech_timeline": speech_timeline,
            "content_stats": content_stats,
            "whisper_diagnostics": diagnostics,
            "model_notes": model_notes,
        }

"""SoAI - Application media parsing service ownership [backend/app/media_parsing_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.files.protocols import DocumentReaderProtocol, FileParserProtocol
    from core.media.protocols import (
        MediaOcrRuntimeProtocol,
        MediaTranscriptionRuntimeProtocol,
    )
    from files.parsers.tika_runtime import TikaRuntime
    from mcp.tools.read_audio_service import ReadAudioService

__all__ = ("MediaParsingServices",)


@dataclass(frozen=True, slots=True)
class MediaParsingServices:
    tika_runtime: TikaRuntime
    transcription_runtime: MediaTranscriptionRuntimeProtocol
    ocr_runtime: MediaOcrRuntimeProtocol
    parser_registry: dict[str, FileParserProtocol]
    document_reader: DocumentReaderProtocol
    read_audio_service: ReadAudioService

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MediaParsingServices",
            tika_runtime=self.tika_runtime,
            transcription_runtime=self.transcription_runtime,
            ocr_runtime=self.ocr_runtime,
            parser_registry=self.parser_registry,
            document_reader=self.document_reader,
            read_audio_service=self.read_audio_service,
        )

    def parser_registry_factory(self) -> dict[str, FileParserProtocol]:
        return self.parser_registry

    async def start(self) -> None:
        await self.tika_runtime.start()

    async def shutdown(self) -> None:
        results = await asyncio.gather(
            self.tika_runtime.shutdown(),
            self.transcription_runtime.shutdown(),
            self.ocr_runtime.shutdown(),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, asyncio.CancelledError):
                raise result
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            raise ExceptionGroup("Media parsing runtime shutdown failed.", failures)

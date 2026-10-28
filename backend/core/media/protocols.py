"""SoAI - Shared media runtime protocols [backend/core/media/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.ipc.protocols import IpcConnectionWaitServerProtocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy

    from core.media.speech_catalog import SpeechCatalogSnapshot
    from core.media.speech_selection import ResolvedSpeechModel
    from core.media.speech_setup import SpeechTask
    from core.media.transcription_contracts import (
        MediaTranscriptionRequest,
        SpeechChunkRequest,
    )
    from core.media.types import (
        OcrFrameText,
        TranscriptionChunkResult,
        TranscriptionResult,
    )
    from core.types.json import JSONValue

    type OcrCoordinate = int | float
    type OcrBoundingBox = Sequence[Sequence[OcrCoordinate]]
    type OcrResult = tuple[OcrBoundingBox, str, float]
    type OcrRawValue = OcrBoundingBox | str | float | int
    type OcrRawEntry = Sequence[OcrRawValue]

__all__ = (
    "MediaIpcServerLifecycleProtocol",
    "MediaOcrRuntimeProtocol",
    "MediaTranscriptionRuntimeProtocol",
    "OcrEngineProtocol",
    "SpeechCatalogProtocol",
    "TranscriptionChunkGatewayProtocol",
)


class OcrEngineProtocol(Protocol):
    def __call__(
        self,
        image: numpy.ndarray,
    ) -> tuple[Sequence[OcrRawEntry] | None, JSONValue]: ...


class MediaIpcServerLifecycleProtocol(IpcConnectionWaitServerProtocol, Protocol):
    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...


class MediaOcrRuntimeProtocol(Protocol):
    async def read_frame(
        self,
        *,
        frame_path: str,
        ocr_language: str,
        timestamp_seconds: float,
        timeout_seconds: float,
    ) -> OcrFrameText: ...

    async def shutdown(self) -> None: ...


class MediaTranscriptionRuntimeProtocol(Protocol):
    async def resolve_model(self, *, selector: str, task: SpeechTask) -> ResolvedSpeechModel: ...

    async def transcribe(self, request: MediaTranscriptionRequest) -> TranscriptionResult: ...

    async def shutdown(self) -> None: ...


class SpeechCatalogProtocol(Protocol):
    async def snapshot_speech_catalog(self) -> SpeechCatalogSnapshot: ...


class TranscriptionChunkGatewayProtocol(Protocol):
    async def resolve_model(self, *, selector: str, task: SpeechTask) -> ResolvedSpeechModel: ...

    async def transcribe_chunk(self, request: SpeechChunkRequest) -> TranscriptionChunkResult: ...

    async def shutdown(self) -> None: ...

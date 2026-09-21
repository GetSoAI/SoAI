"""SoAI - Shared media runtime protocols [backend/core/media/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.ipc.protocols import IpcConnectionWaitServerProtocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    import numpy

    from core.files.types import ParseProgressCallback
    from core.media.types import OcrFrameText, TranscriptionResult
    from core.types.json import JSONDict, JSONValue

    type OcrCoordinate = int | float
    type OcrBoundingBox = Sequence[Sequence[OcrCoordinate]]
    type OcrResult = tuple[OcrBoundingBox, str, float]
    type OcrRawValue = OcrBoundingBox | str | float | int
    type OcrRawEntry = Sequence[OcrRawValue]

__all__ = (
    "MediaOcrRuntimeProtocol",
    "MediaIpcServerLifecycleProtocol",
    "MediaTranscriptionRuntimeProtocol",
    "OcrEngineProtocol",
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
    ) -> TranscriptionResult: ...

    async def shutdown(self) -> None: ...


class TranscriptionChunkGatewayProtocol(Protocol):
    async def transcribe_chunk(
        self,
        *,
        file_path: str,
        model_name: str,
        language: str | None,
        task: str,
        include_word_timestamps: bool,
        timeout_seconds: float,
    ) -> JSONDict: ...

    async def shutdown(self) -> None: ...

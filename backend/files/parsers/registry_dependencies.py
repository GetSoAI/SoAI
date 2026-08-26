"""SoAI - Parser registry composition dependencies [backend/files/parsers/registry_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.files.protocols import FileParserProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.media.image_preprocessing import ImagePreprocessor
    from core.media.protocols import (
        MediaOcrRuntimeProtocol,
        MediaTranscriptionRuntimeProtocol,
    )

__all__ = ("ParserRegistryDependencies",)


@dataclass(frozen=True, slots=True)
class ParserRegistryDependencies:
    storage_manager: StorageManagerProtocol
    transcription_runtime: MediaTranscriptionRuntimeProtocol
    ocr_runtime: MediaOcrRuntimeProtocol
    tika_parser: FileParserProtocol
    image_preprocessor: ImagePreprocessor | None
    config: ConfigProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ParserRegistryDependencies",
            storage_manager=self.storage_manager,
            transcription_runtime=self.transcription_runtime,
            ocr_runtime=self.ocr_runtime,
            tika_parser=self.tika_parser,
            config=self.config,
        )

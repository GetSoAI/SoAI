"""SoAI - Image parsing with EXIF extraction and OCR [backend/files/parsers/media/image_parser.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import override

import numpy
import pi_heif
from PIL import Image, UnidentifiedImageError

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.types import ParsedDocument
from core.imports.availability import module_available, require_module
from core.logging.protocols import StandardLogger
from core.media.image_preprocessing import ImagePreprocessor
from core.media.ocr_engine import (
    DEFAULT_OCR_CONFIDENCE_THRESHOLD,
    ocr_readtext,
    ocr_readtext_multipass,
    ocr_tesseract_image_to_text,
)
from files.parsers.media.image_exif_metadata import apply_exif_metadata
from files.parsers.media_parser import BaseMediaParser

__all__ = (
    "ImageParser",
    "ImageParserConfig",
    "ImageParserDependencies",
)

OPERATION_FILE_PARSERS_CLOSE_IMAGE = "file_parsers.close_image"
OPERATION_FILE_PARSERS_EXTRACT_EXIF = "file_parsers.extract_exif"
OPERATION_FILE_PARSERS_OCR = "file_parsers.ocr"
OPERATION_FILE_PARSERS_TESSERACT_OCR = "file_parsers.tesseract_ocr"
EXIF_METADATA_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    FileNotFoundError,
)
TESSERACT_OCR_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    FileNotFoundError,
)


@dataclass(frozen=True, slots=True)
class ImageParserConfig:
    enable_ocr: bool = True
    ocr_confidence_threshold: float = DEFAULT_OCR_CONFIDENCE_THRESHOLD
    enable_preprocessing: bool = True
    enable_multipass: bool = True


@dataclass(frozen=True, slots=True)
class ImageParserDependencies:
    config: ImageParserConfig
    preprocessor: ImagePreprocessor | None
    logger: StandardLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ImageParserDependencies",
            config=self.config,
            logger=self.logger,
        )


class ImageParser(BaseMediaParser):
    def __init__(self, deps: ImageParserDependencies) -> None:
        self._config = deps.config
        self._preprocessor = deps.preprocessor
        self._logger = deps.logger

    @override
    def parse_blocking(self, file_path: str) -> ParsedDocument:
        require_module("PIL", feature="Image parsing")
        if file_path.lower().endswith((".heic", ".heif")):
            require_module("pi_heif", feature="HEIC/HEIF image parsing")
            pi_heif.register_heif_opener()
        metadata, _ = self._init_media_context(file_path)
        text_parts: list[str] = []
        try:
            opened = Image.open(file_path)
            try:
                metadata.update(
                    {
                        "width": opened.width,
                        "height": opened.height,
                        "format": opened.format,
                    },
                )
                if opened.mode:
                    metadata["mode"] = opened.mode
                try:
                    apply_exif_metadata(metadata, opened)
                except EXIF_METADATA_EXCEPTIONS as error:
                    log_handled_exception(
                        self._logger,
                        error,
                        message="Failed to extract EXIF from image (non-critical).",
                        operation=OPERATION_FILE_PARSERS_EXTRACT_EXIF,
                        details={"path": file_path},
                        level="debug",
                    )
                pil_image_source: Image.Image = opened
                if self._config.enable_ocr and pil_image_source.mode not in (
                    "RGB",
                    "L",
                ):
                    pil_image_source = pil_image_source.convert("RGB")
                pil_image: Image.Image = pil_image_source.copy()
            finally:
                try:
                    opened.close()
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        self._logger,
                        exception,
                        message="Failed to close opened image handle (non-critical).",
                        operation=OPERATION_FILE_PARSERS_CLOSE_IMAGE,
                        details={"path": file_path},
                        level="debug",
                    )
        except Image.DecompressionBombError as error:
            raise ValidationError(
                f"Image too large or suspiciously large (possible decompression bomb): {error}",
            ) from error
        except UnidentifiedImageError as error:
            raise ValidationError("Unsupported or corrupted image file") from error
        if self._config.enable_ocr:
            require_module("numpy", feature="OCR image processing")
            if pil_image.mode in ("I", "I;16", "I;16B", "I;16L"):
                arr = numpy.array(pil_image)
                arr_8bit = (arr / 256).astype(numpy.uint8)
                pil_image = Image.fromarray(arr_8bit)
            if pil_image.mode not in ("RGB", "L"):
                pil_image = pil_image.convert("RGB")
            image_np = numpy.array(pil_image)
            try:
                if self._config.enable_preprocessing and module_available("cv2"):
                    preprocessor = self._preprocessor
                    if preprocessor is None:
                        raise ValidationError(
                            "Image preprocessing requires ImagePreprocessor but none was configured.",
                        )
                    is_complex, _ = preprocessor.detect_complexity(image_np)
                    if is_complex and self._config.enable_multipass:
                        variants = preprocessor.preprocess_complex(image_np)
                        results = ocr_readtext_multipass(variants)
                    else:
                        processed = preprocessor.preprocess_simple(image_np)
                        results = ocr_readtext(processed)
                else:
                    results = ocr_readtext(image_np)
                for _, text, confidence in results:
                    if confidence > self._config.ocr_confidence_threshold:
                        text_parts.append(text)
                if text_parts:
                    metadata["ocr_engine"] = "rapidocr"
            except RECOVERABLE_EXCEPTIONS as error:
                log_handled_exception(
                    self._logger,
                    error,
                    message="OCR failed for image (non-critical).",
                    operation=OPERATION_FILE_PARSERS_OCR,
                    details={"path": file_path},
                    level="debug",
                )
            if not text_parts:
                try:
                    tesseract_text = ocr_tesseract_image_to_text(pil_image)
                    if tesseract_text:
                        text_parts.append(tesseract_text)
                        metadata["ocr_engine"] = "tesseract"
                except TESSERACT_OCR_EXCEPTIONS as error:
                    log_handled_exception(
                        self._logger,
                        error,
                        message="Tesseract OCR failed for image (non-critical).",
                        operation=OPERATION_FILE_PARSERS_TESSERACT_OCR,
                        details={"path": file_path},
                        level="debug",
                    )
        return ParsedDocument(content=self._join_content(text_parts), metadata=metadata)

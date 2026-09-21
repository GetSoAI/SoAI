"""SoAI - Shared RapidOCR and Tesseract execution [backend/core/media/ocr_engine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
import os
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import numpy
import pytesseract
from PIL import Image

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.imports.availability import module_available, require_module
from core.logging.trace import get_logger
from core.media.image_preprocessing import (
    ImagePreprocessor,
    ImagePreprocessorConfig,
    ImagePreprocessorDependencies,
)
from core.media.opencv_backend import create_optional_opencv_api
from core.media.tesseract_data import require_tesseract_data_root, require_tesseract_model
from core.media.tesseract_languages import require_ocr_language
from core.timing.constants import OCR_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.media.protocols import (
        OcrBoundingBox,
        OcrEngineProtocol,
        OcrRawEntry,
        OcrResult,
    )

__all__ = (
    "DEFAULT_OCR_CONFIDENCE_THRESHOLD",
    "configure_tesseract_runtime",
    "ocr_image_file",
    "ocr_readtext",
    "ocr_readtext_multipass",
    "ocr_tesseract_image_to_text",
)

DEFAULT_OCR_CONFIDENCE_THRESHOLD = 0.3
LOGGER_NAME = "SoAI.core.media.ocr_engine"
OPERATION = "core.media.ocr_engine.multipass_variant"


def configure_tesseract_runtime(executable: str, data_directory: str) -> None:
    resolved_executable = os.path.abspath(executable)
    resolved_data_directory = os.path.abspath(data_directory)
    if not os.path.isfile(resolved_executable):
        raise StateError("Managed Tesseract executable is missing.")
    require_tesseract_data_root(resolved_data_directory)
    pytesseract.pytesseract.tesseract_cmd = resolved_executable
    os.environ["SOAI_TESSERACT_CMD"] = resolved_executable
    os.environ["TESSDATA_PREFIX"] = resolved_data_directory


def _raise_rapid_ocr_unavailable() -> OcrEngineProtocol:
    require_module("rapidocr_onnxruntime", feature="OCR")
    require_module("cv2", feature="RapidOCR")
    raise StateError("RapidOCR is unavailable.")


rapid_ocr_engine_builder: Callable[[], OcrEngineProtocol] = _raise_rapid_ocr_unavailable
if module_available("rapidocr_onnxruntime") and module_available("cv2"):
    from rapidocr_onnxruntime import RapidOCR

    def _build_rapid_ocr_engine() -> OcrEngineProtocol:
        return RapidOCR()

    rapid_ocr_engine_builder = _build_rapid_ocr_engine


@functools.cache
def _get_ocr_engine() -> OcrEngineProtocol:
    require_module("rapidocr_onnxruntime", feature="OCR")
    require_module("cv2", feature="RapidOCR")
    return rapid_ocr_engine_builder()


@functools.cache
def _get_ocr_preprocessor() -> ImagePreprocessor | None:
    opencv_api = create_optional_opencv_api()
    if opencv_api is None:
        return None
    return ImagePreprocessor(
        ImagePreprocessorDependencies(
            opencv_api=opencv_api,
            config=ImagePreprocessorConfig(),
            logger=get_logger(LOGGER_NAME),
        ),
    )


def ocr_readtext(image: numpy.ndarray) -> list[OcrResult]:
    results, _diagnostics = _get_ocr_engine()(image)
    normalized: list[OcrResult] = []
    for entry in results or ():
        normalized_entry = _normalize_entry(entry)
        if normalized_entry is not None:
            normalized.append(normalized_entry)
    return normalized


def _normalize_entry(entry: OcrRawEntry) -> OcrResult | None:
    if len(entry) < 3:
        return None
    bounding_box, text, confidence = entry[0], entry[1], entry[2]
    if not isinstance(text, str) or not isinstance(confidence, int | float):
        return None
    if not isinstance(bounding_box, list | tuple):
        return None
    return bounding_box, " ".join(text.split()), float(confidence)


def ocr_readtext_multipass(image_variants: Sequence[numpy.ndarray]) -> list[OcrResult]:
    logger = get_logger(LOGGER_NAME)
    selected: dict[str, OcrResult] = {}
    for variant in image_variants:
        try:
            for result in ocr_readtext(variant):
                _record_best_ocr_result(selected, result)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Multi-pass OCR variant failed (non-critical).",
                operation=OPERATION,
                level="debug",
            )
    values = list(selected.values())
    values.sort(key=lambda item: (_get_bbox_y(item[0]), _get_bbox_x(item[0])))
    return values


def _text_similar(first: str, second: str) -> bool:
    if abs(len(first) - len(second)) > 2:
        return False
    if len(first) < 3 or len(second) < 3:
        return first == second
    distance = sum(left != right for left, right in zip(first, second, strict=False))
    distance += abs(len(first) - len(second))
    return distance <= 2


def _record_best_ocr_result(selected: dict[str, OcrResult], result: OcrResult) -> None:
    text_key = "".join(result[1].casefold().split())
    if not text_key:
        return
    existing_key = _find_existing_ocr_text_key(selected, text_key)
    if existing_key is None:
        selected[text_key] = result
        return
    if result[2] > selected[existing_key][2]:
        selected[existing_key] = result


def _find_existing_ocr_text_key(selected: dict[str, OcrResult], text_key: str) -> str | None:
    if text_key in selected:
        return text_key
    for existing_key in selected:
        if _text_similar(text_key, existing_key):
            return existing_key
    return None


def _get_bbox_y(bounding_box: OcrBoundingBox) -> float:
    if bounding_box and len(bounding_box[0]) >= 2:
        return float(bounding_box[0][1])
    return 0.0


def _get_bbox_x(bounding_box: OcrBoundingBox) -> float:
    if bounding_box and bounding_box[0]:
        return float(bounding_box[0][0])
    return 0.0


def ocr_tesseract_image_to_text(
    image: Image.Image,
    *,
    ocr_language: str,
    timeout_sec: float = OCR_TIMEOUT_SEC,
) -> str:
    require_module("pytesseract", feature="Tesseract OCR")
    require_ocr_language(ocr_language)
    _configure_tesseract_from_environment()
    require_tesseract_model(os.environ["TESSDATA_PREFIX"], ocr_language)
    try:
        text = pytesseract.image_to_string(image, lang=ocr_language, timeout=timeout_sec)
    except RuntimeError as exception:
        if "timeout" in str(exception).casefold():
            raise TimeoutError("Image OCR timed out.") from exception
        raise
    except pytesseract.TesseractNotFoundError as exception:
        raise FileNotFoundError("tesseract binary not found") from exception
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _configure_tesseract_from_environment() -> None:
    executable = os.environ.get("SOAI_TESSERACT_CMD", "").strip()
    data_directory = os.environ.get("TESSDATA_PREFIX", "").strip()
    if not executable or not data_directory:
        raise StateError("Managed Tesseract runtime environment is not configured.")
    configure_tesseract_runtime(executable, data_directory)


def ocr_image_file(file_path: str, ocr_language: str) -> tuple[str, float]:
    require_ocr_language(ocr_language)
    with Image.open(file_path) as opened:
        image = opened.convert("RGB")
        image_array = numpy.array(image)
        try:
            preprocessor = _get_ocr_preprocessor()
            if preprocessor is None:
                results = ocr_readtext(image_array)
            else:
                is_complex, _diagnostics = preprocessor.detect_complexity(image_array)
                if is_complex:
                    results = ocr_readtext_multipass(
                        preprocessor.preprocess_complex(image_array),
                    )
                else:
                    results = ocr_readtext(preprocessor.preprocess_simple(image_array))
        except HANDLED_RUNTIME_EXCEPTIONS as exception:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                exception,
                message="RapidOCR frame extraction failed; using Tesseract.",
                operation=OPERATION,
                level="debug",
            )
            results = []
        accepted = [result for result in results if result[2] >= DEFAULT_OCR_CONFIDENCE_THRESHOLD]
        if accepted:
            return "\n".join(result[1] for result in accepted), sum(
                result[2] for result in accepted
            ) / len(accepted)
        text = ocr_tesseract_image_to_text(image, ocr_language=ocr_language)
        return text, 0.0

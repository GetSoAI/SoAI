"""SoAI - Managed Tesseract model integrity and availability [backend/core/media/tesseract_data.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.files.content_hashing import hash_seekable_binary_stream_content
from core.files.path_policy import ensure_path_within_base
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.media.tesseract_languages import get_tesseract_catalog, require_ocr_language

__all__ = (
    "require_tesseract_data_root",
    "require_tesseract_model",
    "tesseract_model_available",
    "require_complete_tesseract_data",
)


def require_tesseract_data_root(data_directory: str) -> None:
    if (
        not data_directory
        or not os.path.isdir(data_directory)
        or os.path.islink(data_directory)
        or os.path.isjunction(data_directory)
    ):
        raise StateError("Managed Tesseract language data directory is unsafe or missing.")


def _require_data_file(data_directory: str, code: str, expected_sha256: str | None) -> None:
    model_path = os.path.join(data_directory, f"{code}.traineddata")
    ensure_path_within_base(
        data_directory, model_path, description="Tesseract model", error_cls=StateError
    )
    try:
        with open_regular_binary_no_symlink(model_path) as handle:
            if not handle.read(1):
                raise StateError("Selected Tesseract language data is empty.")
            if expected_sha256 is not None:
                content_hash = hash_seekable_binary_stream_content(handle)
                if content_hash.sha256_hex != expected_sha256:
                    raise StateError("Tesseract language data digest is invalid.")
    except (OSError, ValidationError) as exception:
        raise StateError(
            "Selected Tesseract language data is unavailable or unsafe."
        ) from exception


def require_tesseract_model(data_directory: str, ocr_language: str) -> None:
    require_ocr_language(ocr_language)
    require_tesseract_data_root(data_directory)
    _require_data_file(data_directory, ocr_language, None)


def tesseract_model_available(data_directory: str, ocr_language: str) -> bool:
    try:
        require_tesseract_model(data_directory, ocr_language)
    except (OSError, StateError):
        return False
    return True


def require_complete_tesseract_data(data_directory: str) -> None:
    require_tesseract_data_root(data_directory)
    for entry in get_tesseract_catalog().data_files():
        _require_data_file(data_directory, entry.code, entry.sha256)

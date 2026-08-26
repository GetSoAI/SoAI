"""SoAI - Upload content-type validation for OpenAI files endpoints [backend/core/files/upload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.files.content_types import normalize_content_type
from core.files.mime_detection import detect_mime_type
from core.logging.trace import get_logger
from core.validation.integers import is_strict_int

__all__ = (
    "normalize_non_negative_size",
    "normalize_non_negative_size_strict",
    "normalize_positive_size_strict",
    "validate_upload_file_type",
)

LOGGER_NAME = "SoAI.core.files.upload_validation"


_AUDIO_MIME_TYPES: frozenset[str] = frozenset(
    (
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/ogg",
        "audio/flac",
        "audio/x-flac",
        "audio/webm",
        "audio/aac",
    ),
)

_DOCUMENT_MIME_TYPES: frozenset[str] = frozenset(
    (
        "application/pdf",
        "text/plain",
        "text/csv",
        "text/html",
        "text/markdown",
        "application/json",
        "application/xml",
        "text/xml",
        "application/x-yaml",
        "text/yaml",
        "text/x-python",
        "text/x-java-source",
        "text/x-c",
        "text/x-c++",
        "application/javascript",
        "text/javascript",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/epub+zip",
        "application/rtf",
    ),
)

_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    (
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "image/heic",
        "image/heif",
    ),
)

_JSON_MIME_TYPES: frozenset[str] = frozenset(
    ("application/json", "application/jsonl", "application/x-ndjson", "text/plain"),
)


def _allowed_mime_types_by_purpose() -> dict[str, frozenset[str]]:
    return {
        "assistants": _DOCUMENT_MIME_TYPES | _AUDIO_MIME_TYPES | _IMAGE_MIME_TYPES,
        "vision": _IMAGE_MIME_TYPES,
        "fine-tune": _JSON_MIME_TYPES | _AUDIO_MIME_TYPES,
        "retrieval": frozenset(
            (
                "application/pdf",
                "text/plain",
                "text/csv",
                "text/html",
                "text/markdown",
                "application/json",
            ),
        ),
        "batch": frozenset(
            (
                "application/json",
                "application/jsonl",
                "application/x-ndjson",
            ),
        ),
        "audio": _AUDIO_MIME_TYPES,
    }


def _allowed_mime_types_global(allowed_by_purpose: dict[str, frozenset[str]]) -> frozenset[str]:
    return frozenset(mime_type for group in allowed_by_purpose.values() for mime_type in group)


def normalize_non_negative_size(value: int | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    normalized_value = int(value)
    if normalized_value < 0:
        raise ValidationError(f"{field_name} must be >= 0.")
    return normalized_value


def normalize_non_negative_size_strict(value: int | None, *, field_name: str) -> int | None:
    if isinstance(value, bool):
        raise ValidationError(f"{field_name} must be an integer.")
    return normalize_non_negative_size(value, field_name=field_name)


def normalize_positive_size_strict(value: int, *, field_name: str) -> int:
    if not is_strict_int(value):
        raise ValidationError(f"{field_name} must be a positive integer.")
    if value <= 0:
        raise ValidationError(f"{field_name} must be a positive integer.")
    return value


def _mime_types_compatible(declared: str, detected: str) -> bool:
    if declared == detected:
        return True
    if declared.startswith("text/") and detected.startswith("text/"):
        return True
    if declared in {"application/json", "text/plain"} and detected in {
        "application/json",
        "text/plain",
    }:
        return True
    return False


def validate_upload_file_type(
    *,
    content_type: str | None,
    file_content_sample: bytes,
    purpose: str,
    filename: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    allowed_by_purpose = _allowed_mime_types_by_purpose()
    allowed_global = _allowed_mime_types_global(allowed_by_purpose)
    allowed_types = allowed_by_purpose.get(purpose, allowed_global)

    normalized_content_type = normalize_content_type(content_type) or None
    detected_mime_normalized = None
    if file_content_sample:
        detected_mime = detect_mime_type(file_content_sample, filename=filename)
        detected_mime_normalized = normalize_content_type(detected_mime) or None

    content_type_validated = False
    magic_validated = False

    if normalized_content_type:
        if normalized_content_type not in allowed_types:
            raise ValidationError(
                f"Content type '{normalized_content_type}' is not allowed for purpose '{purpose}'.",
            )
        content_type_validated = True

    if detected_mime_normalized:
        if detected_mime_normalized not in allowed_types:
            raise ValidationError(
                f"Detected file type '{detected_mime_normalized}' is not allowed for purpose '{purpose}'.",
            )
        magic_validated = True

    if normalized_content_type and detected_mime_normalized:
        if detected_mime_normalized != normalized_content_type and not _mime_types_compatible(
            normalized_content_type,
            detected_mime_normalized,
        ):
            logger.warning(
                "MIME type mismatch: declared=%s, detected=%s, filename=%s",
                normalized_content_type,
                detected_mime_normalized,
                filename or "unknown",
            )

    if not content_type_validated and not magic_validated:
        raise ValidationError(
            "File type validation failed: unable to determine file type. Provide a valid Content-Type header or ensure the file has recognizable content.",
        )

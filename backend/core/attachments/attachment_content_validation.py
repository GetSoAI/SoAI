"""SoAI - WebUI attachment content part validation [backend/core/attachments/attachment_content_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ITEM_STATUSES,
    KNOWLEDGE_OPERATION_TYPES,
    KNOWLEDGE_SOURCE_TYPES,
)
from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_optional_non_negative_int_strict,
)
from core.validation.strings import require_bounded_trimmed_text

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "SOURCE_ATTACHMENT_UNAVAILABLE_REASON",
    "require_knowledge_source_type",
    "validate_soai_file_content_part",
    "validate_soai_file_unavailable_content_part",
    "validate_soai_knowledge_content_part",
    "validate_soai_knowledge_unavailable_content_part",
)

_SOAI_FILE_ALLOWED_FIELDS = frozenset(
    (
        "type",
        "attachment_id",
        "file_id",
        "filename",
        "mime_type",
        "size_bytes",
        "preview_type",
        "attachment_revision",
        "created_at_ms",
    ),
)

_SOAI_KNOWLEDGE_ALLOWED_FIELDS = frozenset(
    (
        "type",
        "knowledge_attachment_id",
        "summary_id",
        "source_type",
        "operation_type",
        "title",
        "total_count",
        "visible_count",
        "hidden_count",
        "status_counts",
        "attachment_revision",
        "first_event_id",
        "last_event_id",
        "created_at_ms",
        "finalized_at_ms",
    ),
)

_SOAI_FILE_UNAVAILABLE_ALLOWED_FIELDS = frozenset(
    ("type", "filename", "mime_type", "size_bytes", "preview_type", "reason"),
)
_SOAI_KNOWLEDGE_UNAVAILABLE_ALLOWED_FIELDS = frozenset(
    ("type", "title", "source_type", "reason"),
)

_PREVIEW_TYPES = frozenset(("text", "image", "audio", "video", "document", "file"))
_MAX_ID_LENGTH = 128
_MAX_FILENAME_LENGTH = 512
_MAX_MIME_TYPE_LENGTH = 256
_MAX_PREVIEW_TYPE_LENGTH = 32
_MAX_TITLE_LENGTH = 512
_MAX_KNOWLEDGE_TYPE_LENGTH = 64
SOURCE_ATTACHMENT_UNAVAILABLE_REASON = "source_attachment_unavailable"


def require_knowledge_source_type(value: JSONValue) -> str:
    source_type = _require_string(
        value,
        message="SoAI knowledge source_type is required.",
        max_length=_MAX_KNOWLEDGE_TYPE_LENGTH,
    )
    if source_type not in KNOWLEDGE_SOURCE_TYPES:
        raise ValidationError("SoAI knowledge source_type is unsupported.")
    return source_type


def _require_string(value: JSONValue, *, message: str, max_length: int) -> str:
    return require_bounded_trimmed_text(
        value,
        type_message=message,
        empty_message=message,
        max_length=max_length,
        max_length_message=message,
        nul_message=message,
    )


def _require_status_counts(value: JSONValue) -> JSONDict:
    if not isinstance(value, dict):
        raise ValidationError("SoAI knowledge status_counts must be an object.")
    counts: JSONDict = {}
    for key, count_value in value.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or "\x00" in key
            or len(key.strip()) > _MAX_KNOWLEDGE_TYPE_LENGTH
            or key.strip() not in KNOWLEDGE_ITEM_STATUSES
        ):
            raise ValidationError("SoAI knowledge status_counts contains an invalid key.")
        counts[key.strip()] = require_non_negative_int_strict(
            count_value,
            error_message="SoAI knowledge status_counts values must be non-negative integers.",
        )
    return counts


def validate_soai_file_content_part(part: JSONDict) -> JSONDict:
    for field_name in part:
        if field_name not in _SOAI_FILE_ALLOWED_FIELDS:
            raise ValidationError(
                f"SoAI file content part contains unsupported field '{field_name}'.",
            )
    if part.get("type") != "soai_file":
        raise ValidationError("SoAI file content part type must be 'soai_file'.")
    validated: JSONDict = {
        "type": "soai_file",
        "attachment_id": _require_string(
            part.get("attachment_id"),
            message="SoAI file attachment_id must be a non-empty string.",
            max_length=_MAX_ID_LENGTH,
        ),
        "file_id": _require_string(
            part.get("file_id"),
            message="SoAI file file_id must be a non-empty string.",
            max_length=_MAX_ID_LENGTH,
        ),
        "filename": _require_string(
            part.get("filename"),
            message="SoAI file filename must be a non-empty string.",
            max_length=_MAX_FILENAME_LENGTH,
        ),
        "mime_type": _require_string(
            part.get("mime_type"),
            message="SoAI file mime_type must be a non-empty string.",
            max_length=_MAX_MIME_TYPE_LENGTH,
        ),
        "size_bytes": require_non_negative_int_strict(
            part.get("size_bytes"),
            error_message="SoAI file size_bytes must be a non-negative integer.",
        ),
        "preview_type": _require_string(
            part.get("preview_type"),
            message="SoAI file preview_type must be a non-empty string.",
            max_length=_MAX_PREVIEW_TYPE_LENGTH,
        ),
        "attachment_revision": require_non_negative_int_strict(
            part.get("attachment_revision"),
            error_message="SoAI file attachment_revision must be a non-negative integer.",
        ),
        "created_at_ms": require_unix_epoch_ms(
            part.get("created_at_ms"),
            error_message="SoAI file created_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        ),
    }
    if validated["preview_type"] not in _PREVIEW_TYPES:
        raise ValidationError("SoAI file preview_type is invalid.")
    return validated


def validate_soai_file_unavailable_content_part(part: JSONDict) -> JSONDict:
    if set(part) != _SOAI_FILE_UNAVAILABLE_ALLOWED_FIELDS:
        raise ValidationError("SoAI unavailable file content part has unsupported fields.")
    if part.get("type") != "soai_file_unavailable":
        raise ValidationError(
            "SoAI unavailable file content part type must be 'soai_file_unavailable'.",
        )
    preview_type = _require_string(
        part.get("preview_type"),
        message="SoAI unavailable file preview_type must be a non-empty string.",
        max_length=_MAX_PREVIEW_TYPE_LENGTH,
    )
    if preview_type not in _PREVIEW_TYPES:
        raise ValidationError("SoAI unavailable file preview_type is invalid.")
    reason = _require_string(
        part.get("reason"),
        message="SoAI unavailable file reason must be a non-empty string.",
        max_length=_MAX_KNOWLEDGE_TYPE_LENGTH,
    )
    if reason != SOURCE_ATTACHMENT_UNAVAILABLE_REASON:
        raise ValidationError("SoAI unavailable file reason is invalid.")
    return {
        "type": "soai_file_unavailable",
        "filename": _require_string(
            part.get("filename"),
            message="SoAI unavailable file filename must be a non-empty string.",
            max_length=_MAX_FILENAME_LENGTH,
        ),
        "mime_type": _require_string(
            part.get("mime_type"),
            message="SoAI unavailable file mime_type must be a non-empty string.",
            max_length=_MAX_MIME_TYPE_LENGTH,
        ),
        "size_bytes": require_non_negative_int_strict(
            part.get("size_bytes"),
            error_message="SoAI unavailable file size_bytes must be a non-negative integer.",
        ),
        "preview_type": preview_type,
        "reason": reason,
    }


def validate_soai_knowledge_content_part(part: JSONDict) -> JSONDict:
    for field_name in part:
        if field_name not in _SOAI_KNOWLEDGE_ALLOWED_FIELDS:
            raise ValidationError(
                f"SoAI knowledge content part contains unsupported field '{field_name}'.",
            )
    if part.get("type") != "soai_knowledge":
        raise ValidationError("SoAI knowledge content part type must be 'soai_knowledge'.")
    source_type = require_knowledge_source_type(part.get("source_type"))
    operation_type = _require_string(
        part.get("operation_type"),
        message="SoAI knowledge operation_type must be a non-empty string.",
        max_length=_MAX_KNOWLEDGE_TYPE_LENGTH,
    )
    if operation_type not in KNOWLEDGE_OPERATION_TYPES:
        raise ValidationError("SoAI knowledge operation_type is invalid.")
    validated: JSONDict = {
        "type": "soai_knowledge",
        "knowledge_attachment_id": _require_string(
            part.get("knowledge_attachment_id"),
            message="SoAI knowledge knowledge_attachment_id must be a non-empty string.",
            max_length=_MAX_ID_LENGTH,
        ),
        "summary_id": _require_string(
            part.get("summary_id"),
            message="SoAI knowledge summary_id must be a non-empty string.",
            max_length=_MAX_ID_LENGTH,
        ),
        "source_type": source_type,
        "operation_type": operation_type,
        "title": _require_string(
            part.get("title"),
            message="SoAI knowledge title must be a non-empty string.",
            max_length=_MAX_TITLE_LENGTH,
        ),
        "total_count": require_non_negative_int_strict(
            part.get("total_count"),
            error_message="SoAI knowledge total_count must be a non-negative integer.",
        ),
        "visible_count": require_non_negative_int_strict(
            part.get("visible_count"),
            error_message="SoAI knowledge visible_count must be a non-negative integer.",
        ),
        "hidden_count": require_non_negative_int_strict(
            part.get("hidden_count"),
            error_message="SoAI knowledge hidden_count must be a non-negative integer.",
        ),
        "status_counts": _require_status_counts(part.get("status_counts")),
        "attachment_revision": require_non_negative_int_strict(
            part.get("attachment_revision"),
            error_message="SoAI knowledge attachment_revision must be a non-negative integer.",
        ),
        "first_event_id": require_optional_non_negative_int_strict(
            part.get("first_event_id"),
            error_message="SoAI knowledge first_event_id must be a non-negative integer.",
        ),
        "last_event_id": require_optional_non_negative_int_strict(
            part.get("last_event_id"),
            error_message="SoAI knowledge last_event_id must be a non-negative integer.",
        ),
        "created_at_ms": require_unix_epoch_ms(
            part.get("created_at_ms"),
            error_message="SoAI knowledge created_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        ),
        "finalized_at_ms": require_unix_epoch_ms(
            part.get("finalized_at_ms"),
            error_message="SoAI knowledge finalized_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        ),
    }
    return validated


def validate_soai_knowledge_unavailable_content_part(part: JSONDict) -> JSONDict:
    if set(part) != _SOAI_KNOWLEDGE_UNAVAILABLE_ALLOWED_FIELDS:
        raise ValidationError("SoAI unavailable knowledge content part has unsupported fields.")
    if part.get("type") != "soai_knowledge_unavailable":
        raise ValidationError(
            "SoAI unavailable knowledge content part type must be 'soai_knowledge_unavailable'.",
        )
    reason = _require_string(
        part.get("reason"),
        message="SoAI unavailable knowledge reason must be a non-empty string.",
        max_length=_MAX_KNOWLEDGE_TYPE_LENGTH,
    )
    if reason != SOURCE_ATTACHMENT_UNAVAILABLE_REASON:
        raise ValidationError("SoAI unavailable knowledge reason is invalid.")
    return {
        "type": "soai_knowledge_unavailable",
        "title": _require_string(
            part.get("title"),
            message="SoAI unavailable knowledge title must be a non-empty string.",
            max_length=_MAX_TITLE_LENGTH,
        ),
        "source_type": require_knowledge_source_type(part.get("source_type")),
        "reason": reason,
    }

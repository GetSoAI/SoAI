"""SoAI - Conversation PDF export metadata validation [backend/features/api/routes/webui/conversation_pdf_export_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import string
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import coerce_exact_int_or_none

__all__ = (
    "ConversationPdfExportMetadata",
    "parse_conversation_pdf_export_metadata",
    "require_expected_conversation_pdf_digest",
)

_MAX_FOOTER_LABEL_LENGTH = 160
_SHA256_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class ConversationPdfExportMetadata:
    title: str
    export_date: str
    small_logo_data_uri: str
    expected_html_sha256: str | None
    expected_cover_sha256: str | None
    conversation_id: str
    expected_last_modified_at_ms: int
    footer_note_label: str
    footer_pages_label: str


def _single_value(fields: dict[str, tuple[str, ...]], name: str) -> str:
    values = fields.get(name)
    if values is not None and len(values) != 1:
        raise ValidationError(f"PDF export field '{name}' must be provided exactly once.")
    return values[0].strip() if values else ""


def _field(fields: dict[str, tuple[str, ...]], name: str, *, max_length: int) -> str:
    value = _single_value(fields, name)
    if not value:
        raise ValidationError(f"Missing PDF export field '{name}'.")
    if len(value) > max_length:
        raise ValidationError(f"PDF export field '{name}' is too long.")
    return value


def _optional_field(
    fields: dict[str, tuple[str, ...]],
    name: str,
    *,
    max_length: int,
) -> str | None:
    value = _single_value(fields, name)
    if not value:
        return None
    if len(value) > max_length:
        raise ValidationError(f"PDF export field '{name}' is too long.")
    return value


def _require_data_uri(value: str, field_name: str) -> str:
    if not value.startswith("data:image/"):
        raise ValidationError(f"PDF export field '{field_name}' must be an image data URI.")
    return value


def _optional_sha256_field(fields: dict[str, tuple[str, ...]], name: str) -> str | None:
    value = _optional_field(fields, name, max_length=_SHA256_HEX_LENGTH)
    if value is None:
        return None
    if len(value) != _SHA256_HEX_LENGTH or any(
        character not in string.hexdigits for character in value
    ):
        raise ValidationError(f"{name} must be 64 hexadecimal characters.")
    return value.lower()


def _parse_epoch_ms_field(fields: dict[str, tuple[str, ...]], name: str) -> int:
    value = _field(fields, name, max_length=32)
    parsed = coerce_exact_int_or_none(value, allow_signed_text=False)
    if parsed is None:
        raise ValidationError(f"PDF export field '{name}' must be an epoch-millisecond integer.")
    return require_unix_epoch_ms(
        parsed,
        error_message=f"PDF export field '{name}' must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )


def require_expected_conversation_pdf_digest(
    expected: str | None,
    actual: str,
    message: str,
) -> None:
    if expected is not None and expected != actual.lower():
        raise ValidationError(message)


def parse_conversation_pdf_export_metadata(
    fields: dict[str, tuple[str, ...]],
) -> ConversationPdfExportMetadata:
    return ConversationPdfExportMetadata(
        title=_field(fields, "title", max_length=250),
        export_date=_field(fields, "export_date", max_length=80),
        small_logo_data_uri=_require_data_uri(
            _field(fields, "small_logo_data_uri", max_length=1_500_000),
            "small_logo_data_uri",
        ),
        expected_html_sha256=_optional_sha256_field(fields, "html_sha256"),
        expected_cover_sha256=_optional_sha256_field(fields, "cover_sha256"),
        conversation_id=_field(fields, "conversation_id", max_length=120),
        expected_last_modified_at_ms=_parse_epoch_ms_field(
            fields,
            "expected_last_modified_at_ms",
        ),
        footer_note_label=_field(
            fields,
            "footer_note_label",
            max_length=_MAX_FOOTER_LABEL_LENGTH,
        ),
        footer_pages_label=_field(
            fields,
            "footer_pages_label",
            max_length=_MAX_FOOTER_LABEL_LENGTH,
        ),
    )

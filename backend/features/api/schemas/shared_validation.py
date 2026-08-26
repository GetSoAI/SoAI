"""SoAI - Shared API schema validation primitives [backend/features/api/schemas/shared_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.strict_numbers import require_positive_int_strict
from core.validation.strings import require_labeled_text

if TYPE_CHECKING:
    from core.meta.soai_v1 import SoAIV1StrictModel

__all__ = (
    "require_client_identifier",
    "require_non_empty_content_when_list",
    "require_non_empty_schema_sequence",
    "require_positive_optional_schema_int",
    "require_schema_text_field",
)


def require_client_identifier(value: str) -> str:
    return require_schema_text_field(
        value,
        field_label="client_id",
        suffix="must be a non-empty string.",
    )


def require_schema_text_field(value: str | None, *, field_label: str, suffix: str) -> str:
    return require_labeled_text(value, field_label=field_label, suffix=suffix)


def require_positive_optional_schema_int(value: int | None, *, error_message: str) -> int | None:
    if value is None:
        return None
    return require_positive_int_strict(value, error_message=error_message)


def require_non_empty_content_when_list(
    value: str | Sequence[SoAIV1StrictModel],
) -> None:
    if isinstance(value, str):
        return
    require_non_empty_schema_sequence(value, label="content")


def require_non_empty_schema_sequence(
    value: Sequence[SoAIV1StrictModel],
    *,
    label: str,
) -> None:
    if not value:
        raise ValidationError(f"{label} must be a non-empty array.")

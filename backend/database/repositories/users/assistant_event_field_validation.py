"""SoAI - Assistant event field validation helpers [backend/database/repositories/users/assistant_event_field_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.strict_numbers import (
    require_non_negative_int_strict,
    require_positive_int_strict,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "validate_assistant_event_assistant_revision",
    "validate_assistant_event_epoch_timestamp",
    "validate_assistant_event_sequence",
    "validate_assistant_event_type",
)


def validate_assistant_event_epoch_timestamp(value: JSONValue | bytes, *, field_name: str) -> int:
    return require_unix_epoch_ms(
        value,
        error_message=f"Assistant event {field_name} must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )


def validate_assistant_event_sequence(value: JSONValue | bytes) -> int:
    if isinstance(value, bytes):
        raise ValidationError("Assistant event sequence must be a non-negative integer.")
    return require_non_negative_int_strict(
        value,
        error_message="Assistant event sequence must be a non-negative integer.",
    )


def validate_assistant_event_assistant_revision(value: JSONValue | bytes) -> int:
    if isinstance(value, bytes):
        raise ValidationError("Assistant event assistant_revision must be a positive integer.")
    return require_positive_int_strict(
        value,
        error_message="Assistant event assistant_revision must be a positive integer.",
    )


def validate_assistant_event_type(value: JSONValue | bytes) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Assistant event type must be a non-empty string.")
    return value.strip()

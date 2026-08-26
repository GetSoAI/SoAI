"""SoAI - Epoch millisecond validation helpers [backend/core/validation/epoch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING, TypeGuard

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "EPOCH_MS_MAX",
    "EPOCH_MS_MIN",
    "is_unix_epoch_ms",
    "normalize_optional_unix_epoch_ms",
    "require_unix_epoch_ms",
)

EPOCH_MS_MIN = 1_000_000_000_000
EPOCH_MS_MAX = 253_402_300_799_999


def require_unix_epoch_ms(
    value: JSONValue | bytes,
    *,
    error_message: str,
    enforce_maximum: bool = True,
) -> int:
    if not is_strict_int(value):
        raise ValidationError(error_message)
    if value < EPOCH_MS_MIN:
        raise ValidationError(error_message)
    if enforce_maximum and value > EPOCH_MS_MAX:
        raise ValidationError(error_message)
    return value


def is_unix_epoch_ms(value: JSONValue | bytes, *, enforce_maximum: bool = True) -> TypeGuard[int]:
    try:
        require_unix_epoch_ms(
            value,
            error_message="Value must be an epoch-millisecond integer.",
            enforce_maximum=enforce_maximum,
        )
    except ValidationError:
        return False
    return True


def normalize_optional_unix_epoch_ms(value: float | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValidationError(f"{field_name} must be an epoch-millisecond integer.")
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValidationError(f"{field_name} must be an epoch-millisecond integer.")
        candidate = int(value)
    elif isinstance(value, int):
        candidate = value
    else:
        raise ValidationError(f"{field_name} must be an epoch-millisecond integer.")
    if candidate < EPOCH_MS_MIN or candidate > EPOCH_MS_MAX:
        raise ValidationError(
            f"{field_name} must be an epoch-millisecond integer between {EPOCH_MS_MIN} and {EPOCH_MS_MAX}.",
        )
    return candidate

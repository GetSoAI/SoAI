"""SoAI - Canonical user_id coercion helpers [backend/core/users/user_id.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, TypeGuard

from core.errors.exceptions import ValidationError
from core.users.protocols import UserIdCarrierProtocol
from core.validation.integers import is_positive_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

    type UserIdValue = JSONValue | UserIdCarrierProtocol

__all__ = (
    "coerce_optional_user_id",
    "coerce_user_id",
    "is_strict_user_id",
    "require_strict_user_id",
    "require_user_id",
)


def _unwrap_user_id(value: UserIdValue) -> int | float | str | bool | None:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Mapping):
        candidate = value.get("user_id")
        if candidate is None or isinstance(candidate, bool | int | float | str):
            return candidate
        return None
    if not isinstance(value, UserIdCarrierProtocol):
        return None
    candidate = value.user_id
    if candidate is None or isinstance(candidate, bool | int | float | str):
        return candidate
    return None


def coerce_optional_user_id(value: UserIdValue) -> int | None:
    unwrapped = _unwrap_user_id(value)
    if unwrapped is None or isinstance(unwrapped, bool):
        return None
    if isinstance(unwrapped, int):
        return int(unwrapped)
    if isinstance(unwrapped, float):
        if not math.isfinite(unwrapped):
            return None
        return int(unwrapped)
    if not isinstance(unwrapped, str):
        return None
    normalized = unwrapped.strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except (TypeError, ValueError, OverflowError):
        return None


def coerce_user_id(value: UserIdValue) -> int:
    return coerce_optional_user_id(value) or 0


def is_strict_user_id(value: UserIdValue) -> TypeGuard[int]:
    return is_positive_strict_int(value)


def require_strict_user_id(
    value: UserIdValue,
    *,
    message: str = "user_id must be a positive integer.",
) -> int:
    if not is_strict_user_id(value):
        raise ValidationError(message)
    return int(value)


def require_user_id(value: UserIdValue) -> int:
    user_id = coerce_optional_user_id(value)
    if user_id is None or user_id <= 0:
        raise ValidationError("user_id must be a positive integer.")
    return user_id

"""SoAI - Strict integer type predicate [backend/core/validation/strict_integer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TypeGuard

__all__ = ("is_strict_int",)


def is_strict_int[ValueT](value: ValueT, _value_type: type[ValueT] | None = None) -> TypeGuard[int]:
    _ = _value_type
    return isinstance(value, int) and not isinstance(value, bool)

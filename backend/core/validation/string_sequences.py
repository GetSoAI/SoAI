"""SoAI - String sequence normalization helpers [backend/core/validation/string_sequences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.collections.ordered_uniqueness import unique_sequence
from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue

__all__ = (
    "normalize_delimited_string_sequence",
    "normalize_strict_string_sequence",
    "normalize_string_sequence",
)


def normalize_string_sequence(
    values: Iterable[ConfigValue] | None,
    *,
    sort_result: bool = False,
) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        stripped_value = values.strip()
        return (stripped_value,) if stripped_value else ()
    stripped = [str(value or "").strip() for value in values]
    unique = unique_sequence(stripped, omit_falsy=True)
    if sort_result:
        return tuple(sorted(unique))
    return unique


def normalize_delimited_string_sequence(
    value: ConfigValue | None,
    *,
    label: str,
) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        return normalize_string_sequence(stripped.replace(";", ",").split(","))
    if isinstance(value, list | tuple | set | frozenset):
        return normalize_string_sequence(value)
    raise ValidationError(f"{label} must be a string or a list of strings.")


def normalize_strict_string_sequence(
    values: ConfigValue | None,
    *,
    field_name: str,
) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list | tuple | set):
        raise ValidationError(f"Field '{field_name}' must be a list of strings.")
    items: list[str] = []
    for item in values:
        if not isinstance(item, str):
            raise ValidationError(f"Field '{field_name}' must contain only strings.")
        normalized = item.strip()
        if normalized:
            items.append(normalized)
    return items

"""SoAI - Dependency-free strict JSON decoding [backend/core/serialization/strict_json.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Never

if TYPE_CHECKING:
    from collections.abc import Callable

    type StrictJSONValue = (
        None | bool | int | float | str | list[StrictJSONValue] | dict[str, StrictJSONValue]
    )
    type StrictJSONDecoder = Callable[..., StrictJSONValue]

__all__ = (
    "StrictJSONDuplicateKeyError",
    "StrictJSONNonFiniteError",
    "decode_strict_json",
)


class StrictJSONDuplicateKeyError(ValueError):
    __slots__ = ()


class StrictJSONNonFiniteError(ValueError):
    __slots__ = ()


def _reject_nonfinite_constant(constant: str) -> Never:
    raise StrictJSONNonFiniteError(f"Non-finite JSON number is not allowed: {constant}")


def _reject_duplicate_object_pairs(
    pairs: list[tuple[str, StrictJSONValue]],
) -> dict[str, StrictJSONValue]:
    parsed: dict[str, StrictJSONValue] = {}
    for key, value in pairs:
        if key in parsed:
            raise StrictJSONDuplicateKeyError(f"Duplicate JSON object key is not allowed: {key}")
        parsed[key] = value
    return parsed


def _json_structural_depth_exceeds(raw_text: str, *, limit: int) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for character in raw_text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "{[":
            depth += 1
            if depth > limit:
                return True
        elif character in "}]" and depth > 0:
            depth -= 1
    return False


def decode_strict_json(
    raw: str | bytes,
    *,
    decoder: StrictJSONDecoder,
    field: str = "json",
    max_depth: int | None = None,
    strict_utf8: bool = False,
    reject_duplicate_keys: bool = False,
) -> StrictJSONValue:
    normalized_field = field.strip() or "json"
    if isinstance(raw, bytes):
        try:
            raw_text = raw.decode("utf-8", errors="strict" if strict_utf8 else "replace")
        except UnicodeDecodeError as exception:
            raise ValueError(f"{normalized_field} must be valid UTF-8.") from exception
    else:
        raw_text = raw
    if max_depth is not None and _json_structural_depth_exceeds(raw_text, limit=max_depth):
        raise ValueError(f"{normalized_field} exceeds maximum JSON nesting depth.")
    parsed = decoder(
        raw_text,
        parse_constant=_reject_nonfinite_constant,
        object_pairs_hook=(_reject_duplicate_object_pairs if reject_duplicate_keys else None),
    )
    _validate_strict_json_value(parsed, field=normalized_field)
    return parsed


def _validate_strict_json_value(value: StrictJSONValue, *, field: str) -> None:
    if value is None or isinstance(value, bool | int | str):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StrictJSONNonFiniteError(f"{field} contains a non-finite number.")
        return
    if isinstance(value, list):
        for item in value:
            _validate_strict_json_value(item, field=field)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field} contains a non-text object key.")
            _validate_strict_json_value(item, field=field)
        return
    raise ValueError(f"{field} contains a non-JSON value.")

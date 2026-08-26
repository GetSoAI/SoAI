"""SoAI - Coercion helpers for Pydantic JsonValue payloads [backend/core/types/pydantic_json_value.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json import is_json_value

if TYPE_CHECKING:
    from pydantic.types import JsonValue

    from core.types.json import JSONValue

__all__ = (
    "coerce_to_pydantic_json_dict",
    "coerce_to_pydantic_json_value",
)


def coerce_to_pydantic_json_value(value: JSONValue) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise StateError("JSON object contains a non-string key.")
            result[key] = coerce_to_pydantic_json_value(item)
        return result
    if isinstance(value, Sequence):
        return [coerce_to_pydantic_json_value(item) for item in value]
    raise StateError(f"Value is not JSON-compatible: {type(value).__name__}")


def coerce_to_pydantic_json_dict(payload: Mapping[str, JSONValue]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise StateError("JSON object contains a non-string key.")
        if not is_json_value(value):
            raise StateError(f"Value is not JSON-compatible: {type(value).__name__}")
        result[key] = coerce_to_pydantic_json_value(value)
    return result

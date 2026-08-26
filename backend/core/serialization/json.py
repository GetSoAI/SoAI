"""SoAI - JSON serialization and normalization primitives [backend/core/serialization/json.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import datetime
import ipaddress
import json
import math
import os
import uuid
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.serialization.base64_values import encode_base64_ascii
from core.serialization.json_type_guards import (
    is_json_defaultdict_candidate,
    is_json_deque_candidate,
    is_json_dict_candidate,
    is_json_mapping_candidate,
    is_json_pathlike_candidate,
    is_json_sequence_candidate,
    is_json_set_candidate,
)
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "json_compat_serializer",
    "json_safe_default",
    "normalize_for_json",
    "normalize_to_json_dict",
    "serialize_json_compact_stable",
    "serialize_json_compact_stable_default_str",
    "serialize_json_compact_stable_safe_default",
    "serialize_json_compact_stable_strict",
    "serialize_json_compact_stable_with_default",
    "serialize_json_pretty_sorted",
    "serialize_json_pretty_sorted_default_str",
    "serialize_json_pretty_sorted_safe_default",
    "serialize_json_pretty_sorted_strict",
    "serialize_json_pretty_sorted_with_default",
    "serialize_json_string_strict",
    "try_serialize_json_compact_stable_default_str",
)

_IPADDRESS_TYPES = (
    ipaddress.IPv4Address,
    ipaddress.IPv6Address,
    ipaddress.IPv4Network,
    ipaddress.IPv6Network,
    ipaddress.IPv4Interface,
    ipaddress.IPv6Interface,
)


def _coerce_json_leaf[T](value: T, _value_type: type[T] | None = None) -> tuple[bool, JSONValue]:
    _ = _value_type
    if isinstance(value, Enum):
        return (True, normalize_for_json(value.value))
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return (True, value.isoformat())
    if isinstance(value, datetime.timedelta):
        return (True, value.total_seconds())
    if isinstance(value, Decimal):
        return (True, format(value, "f").rstrip("0").rstrip(".") or "0")
    if isinstance(value, bytes | bytearray):
        return (True, encode_base64_ascii(bytes(value)))
    if isinstance(value, memoryview):
        return (True, encode_base64_ascii(value.tobytes()))
    if isinstance(value, uuid.UUID):
        return (True, str(value))
    if is_json_pathlike_candidate(value):
        raw = os.fspath(value)
        if isinstance(raw, bytes):
            return (True, raw.decode("utf-8", errors="replace"))
        return (True, raw)
    if isinstance(value, _IPADDRESS_TYPES):
        return (True, str(value))
    return (False, None)


def json_compat_serializer[T](value: T, _value_type: type[T] | None = None) -> JSONValue:
    _ = _value_type
    if is_json_set_candidate(value):
        return sorted(value, key=str)
    if is_json_defaultdict_candidate(value):
        return {str(key): item for key, item in value.items()}
    if is_json_deque_candidate(value):
        return list(value)
    handled, leaf_value = _coerce_json_leaf(value)
    if handled:
        return leaf_value
    if is_dataclass(value) and (not isinstance(value, type)):
        return asdict(value)
    if is_json_mapping_candidate(value):
        return {str(key): item for key, item in value.items()}
    raise ValidationError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_safe_default[T](value: T, _value_type: type[T] | None = None) -> JSONValue:
    _ = _value_type
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if is_json_set_candidate(value):
        return sorted(value, key=str)
    handled, leaf_value = _coerce_json_leaf(value)
    if handled:
        return leaf_value
    return repr(value)


def normalize_for_json[T](value: T, _value_type: type[T] | None = None) -> JSONValue:
    _ = _value_type
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError("Cannot normalize a non-finite number as JSON.")
        return value
    if is_json_dict_candidate(value):
        return {str(key): normalize_for_json(item) for key, item in value.items()}
    if is_json_sequence_candidate(value):
        return [normalize_for_json(item) for item in value]
    if is_json_set_candidate(value):
        return sorted(
            (normalize_for_json(item) for item in value),
            key=str,
        )
    if is_json_defaultdict_candidate(value):
        return {str(key): normalize_for_json(item) for key, item in value.items()}
    if is_json_deque_candidate(value):
        return [normalize_for_json(item) for item in value]
    handled, leaf_value = _coerce_json_leaf(value)
    if handled:
        return leaf_value
    if is_dataclass(value) and (not isinstance(value, type)):
        return normalize_for_json(asdict(value))
    if is_json_mapping_candidate(value):
        return {str(key): normalize_for_json(item) for key, item in value.items()}
    raise ValidationError(f"Object of type {type(value).__name__} is not JSON serializable")


def normalize_to_json_dict(value: JSONValue, *, message: str) -> JSONDict:
    normalized = normalize_for_json(value)
    result = coerce_json_dict(normalized)
    if result is None:
        raise StateError(message)
    return result


def serialize_json_compact_stable(value: JSONValue, *, ensure_ascii: bool = True) -> str:
    return json.dumps(
        value,
        default=json_compat_serializer,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        separators=(",", ":"),
        sort_keys=True,
    )


def serialize_json_string_strict(value: str, *, ensure_ascii: bool = True) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        separators=(",", ":"),
    )


def serialize_json_pretty_sorted(value: JSONValue, *, ensure_ascii: bool = True) -> str:
    return json.dumps(
        value,
        default=json_compat_serializer,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        indent=2,
        sort_keys=True,
    )


def serialize_json_compact_stable_strict(value: JSONValue, *, ensure_ascii: bool = True) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        separators=(",", ":"),
        sort_keys=True,
    )


def serialize_json_pretty_sorted_strict(value: JSONValue, *, ensure_ascii: bool = True) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        indent=2,
        sort_keys=True,
    )


def serialize_json_compact_stable_default_str(
    value: JSONValue,
    *,
    ensure_ascii: bool = True,
) -> str:
    return json.dumps(
        value,
        default=str,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        separators=(",", ":"),
        sort_keys=True,
    )


def serialize_json_pretty_sorted_default_str(value: JSONValue, *, ensure_ascii: bool = True) -> str:
    return json.dumps(
        value,
        default=str,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        indent=2,
        sort_keys=True,
    )


def serialize_json_compact_stable_safe_default(
    value: JSONValue,
    *,
    ensure_ascii: bool = True,
) -> str:
    return json.dumps(
        value,
        default=json_safe_default,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        separators=(",", ":"),
        sort_keys=True,
    )


def serialize_json_pretty_sorted_safe_default(
    value: JSONValue,
    *,
    ensure_ascii: bool = True,
) -> str:
    return json.dumps(
        value,
        default=json_safe_default,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        indent=2,
        sort_keys=True,
    )


def serialize_json_compact_stable_with_default(
    value: JSONValue,
    *,
    default: Callable[[JSONValue], JSONValue],
    ensure_ascii: bool = True,
) -> str:
    return json.dumps(
        value,
        default=default,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        separators=(",", ":"),
        sort_keys=True,
    )


def serialize_json_pretty_sorted_with_default(
    value: JSONValue,
    *,
    default: Callable[[JSONValue], JSONValue],
    ensure_ascii: bool = True,
) -> str:
    return json.dumps(
        value,
        default=default,
        allow_nan=False,
        ensure_ascii=bool(ensure_ascii),
        indent=2,
        sort_keys=True,
    )


def try_serialize_json_compact_stable_default_str(
    value: JSONValue,
    *,
    ensure_ascii: bool = True,
) -> str | None:
    try:
        return serialize_json_compact_stable_default_str(value, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError):
        return None

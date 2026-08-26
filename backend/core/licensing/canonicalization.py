"""SoAI - Restricted licensing V1 canonical JSON [backend/core/licensing/canonicalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.errors.exceptions import ValidationError
from core.licensing.constants import (
    MAX_CANONICAL_DEPTH,
    MAX_CANONICAL_INTEGER,
    MAX_CANONICAL_MEMBERS,
    MAX_CANONICAL_STRING_BYTES,
    MAX_SIGNED_DOCUMENT_BYTES,
    MIN_CANONICAL_INTEGER,
)
from core.serialization.json import serialize_json_string_strict
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONValue

__all__ = ("canonicalize_licensing_json", "parse_canonical_licensing_document")


def canonicalize_licensing_json(value: JSONValue) -> bytes:
    _validate_value(value, 0)
    return _serialize(value).encode("utf-8")


def parse_canonical_licensing_document(raw_document: bytes) -> JSONValue:
    if len(raw_document) > MAX_SIGNED_DOCUMENT_BYTES:
        raise ValidationError("Licensing document exceeds the V1 size limit.")
    parsed = parse_json_value(
        raw_document,
        field="licensing document",
        max_depth=MAX_CANONICAL_DEPTH,
        strict_utf8=True,
        reject_duplicate_keys=True,
    )
    canonical = canonicalize_licensing_json(parsed)
    if canonical != raw_document:
        raise ValidationError("Licensing document must use canonical V1 JSON bytes.")
    return parsed


def _validate_value(value: JSONValue, depth: int) -> None:
    if depth > MAX_CANONICAL_DEPTH:
        raise ValidationError("Licensing document nesting exceeds the V1 limit.")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if not MIN_CANONICAL_INTEGER <= value <= MAX_CANONICAL_INTEGER:
            raise ValidationError("Licensing integer is outside the V1 domain.")
        return
    if isinstance(value, float):
        raise ValidationError("Licensing V1 does not permit floating-point values.")
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ValidationError("Licensing string contains an invalid Unicode scalar.")
        if len(value.encode("utf-8")) > MAX_CANONICAL_STRING_BYTES:
            raise ValidationError("Licensing string exceeds the V1 limit.")
        return
    if isinstance(value, Sequence):
        if len(value) > MAX_CANONICAL_MEMBERS:
            raise ValidationError("Licensing array exceeds the V1 member limit.")
        for entry in value:
            _validate_value(entry, depth + 1)
        return
    if not isinstance(value, Mapping):
        raise ValidationError("Licensing document value is outside the JSON domain.")
    if len(value) > MAX_CANONICAL_MEMBERS:
        raise ValidationError("Licensing object exceeds the V1 member limit.")
    for key, entry in value.items():
        _validate_value(key, depth + 1)
        _validate_value(entry, depth + 1)


def _serialize(value: JSONValue) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise ValidationError("Licensing V1 does not permit floating-point values.")
    if isinstance(value, str):
        return serialize_json_string_strict(value, ensure_ascii=False)
    if isinstance(value, Sequence):
        return f"[{','.join(_serialize(entry) for entry in value)}]"
    if not isinstance(value, Mapping):
        raise ValidationError("Licensing document value is outside the JSON domain.")
    members = (
        f"{serialize_json_string_strict(key, ensure_ascii=False)}:{_serialize(value[key])}"
        for key in sorted(value, key=_utf16_sort_key)
    )
    return f"{{{','.join(members)}}}"


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")

"""SoAI - Nested mapping key-only signature hashing [backend/core/serialization/key_signatures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Mapping, Sequence
from struct import pack
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

__all__ = ("calculate_nested_mapping_keys_hash",)

if TYPE_CHECKING:
    type NestedKeySignatureValue = (
        str
        | int
        | float
        | bool
        | None
        | os.PathLike[str]
        | Mapping[str, "NestedKeySignatureValue"]
        | Sequence["NestedKeySignatureValue"]
        | set["NestedKeySignatureValue"]
        | frozenset["NestedKeySignatureValue"]
    )


def _iter_nested_mapping_key_paths(
    value: NestedKeySignatureValue,
    *,
    prefix: tuple[str, ...],
) -> Iterable[tuple[str, ...]]:
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            if not isinstance(raw_key, str) or not raw_key:
                raise ValidationError("Mapping contains a non-string or empty key.")
            path = (*prefix, raw_key) if prefix else (raw_key,)
            yield path
            yield from _iter_nested_mapping_key_paths(nested, prefix=path)
        return
    if isinstance(value, list | tuple | set | frozenset):
        for nested in value:
            if isinstance(nested, Mapping | list | tuple | set | frozenset):
                yield from _iter_nested_mapping_key_paths(nested, prefix=prefix)
        return


def calculate_nested_mapping_keys_hash(value: NestedKeySignatureValue) -> str:
    key_paths = sorted(set(_iter_nested_mapping_key_paths(value, prefix=())))
    hasher = hashlib.sha256()
    for key_path in key_paths:
        for part in key_path:
            part_bytes = part.encode("utf-8")
            hasher.update(pack(">I", len(part_bytes)))
            hasher.update(part_bytes)
        hasher.update(b"\x00")
    return hasher.hexdigest()

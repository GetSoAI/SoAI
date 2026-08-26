"""SoAI - ChromaDB metadata coercion helpers [backend/mcp/storage/chroma_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_chroma_metadata_dict",
    "coerce_chroma_metadata_list",
    "coerce_chroma_metadata_value",
)


def coerce_chroma_metadata_value(
    value: JSONValue,
    *,
    field: str,
) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    raise ValidationError(f"{field} must be a Chroma-compatible metadata scalar.")


def coerce_chroma_metadata_dict(
    metadata: JSONDict,
    *,
    field: str,
) -> Mapping[str, str | int | float | bool | None]:
    out: dict[str, str | int | float | bool | None] = {}
    for key, raw_value in metadata.items():
        if not isinstance(key, str):
            raise ValidationError(f"{field} keys must be strings.")
        out[key] = coerce_chroma_metadata_value(raw_value, field=f"{field}.{key}")
    return out


def coerce_chroma_metadata_list(
    metadatas: list[JSONDict],
    *,
    field: str,
) -> list[Mapping[str, str | int | float | bool | None]]:
    out: list[Mapping[str, str | int | float | bool | None]] = []
    for index, metadata in enumerate(metadatas):
        out.append(coerce_chroma_metadata_dict(metadata, field=f"{field}[{index}]"))
    return out

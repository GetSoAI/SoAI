"""SoAI - Chroma IPC payload coercion to strict Chroma API types [backend/mcp/storage/chroma_payload_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from chromadb.api.types import Include, Metadata, PyEmbedding, Where
from chromadb.base_types import (
    InclusionExclusionOperator,
    LiteralValue,
    LogicalOperator,
    OperatorExpression,
    WhereOperator,
)

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_include",
    "coerce_literal_value",
    "coerce_metadata_list",
    "coerce_operator_expression",
    "coerce_payload_int",
    "coerce_py_embedding_vector",
    "coerce_py_embeddings_list",
    "coerce_query_embeddings",
    "coerce_str_list",
    "coerce_where",
)


def coerce_literal_value(value: JSONValue, field: str) -> LiteralValue:
    if isinstance(value, str | bool):
        return value
    if is_strict_int(value):
        return value
    if isinstance(value, float) and not isinstance(value, bool) and math.isfinite(value):
        return value
    raise ValidationError(f"{field} must be a string, number, or boolean.")


def coerce_operator_expression(value: JSONValue, field: str) -> OperatorExpression:
    if not isinstance(value, dict):
        raise ValidationError(f"{field} operator expression must be a JSON object.")
    in_ops: dict[InclusionExclusionOperator, list[LiteralValue]] = {}
    compare_ops: dict[WhereOperator | LogicalOperator, LiteralValue] = {}
    for key, raw_item in value.items():
        if not isinstance(key, str) or not key:
            raise ValidationError(f"{field} contains an invalid operator key.")
        match key:
            case "$in":
                if not isinstance(raw_item, list):
                    raise ValidationError(f"{field}.{key} must be a list.")
                items: list[LiteralValue] = []
                for item in raw_item:
                    items.append(coerce_literal_value(item, f"{field}.{key}"))
                in_ops["$in"] = items
            case "$nin":
                if not isinstance(raw_item, list):
                    raise ValidationError(f"{field}.{key} must be a list.")
                items = []
                for item in raw_item:
                    items.append(coerce_literal_value(item, f"{field}.{key}"))
                in_ops["$nin"] = items
            case "$gt":
                compare_ops["$gt"] = coerce_literal_value(raw_item, f"{field}.{key}")
            case "$gte":
                compare_ops["$gte"] = coerce_literal_value(raw_item, f"{field}.{key}")
            case "$lt":
                compare_ops["$lt"] = coerce_literal_value(raw_item, f"{field}.{key}")
            case "$lte":
                compare_ops["$lte"] = coerce_literal_value(raw_item, f"{field}.{key}")
            case "$ne":
                compare_ops["$ne"] = coerce_literal_value(raw_item, f"{field}.{key}")
            case "$eq":
                compare_ops["$eq"] = coerce_literal_value(raw_item, f"{field}.{key}")
            case _:
                raise ValidationError(f"{field} contains an unsupported operator: {key}")
    if in_ops:
        if compare_ops:
            raise ValidationError(f"{field} cannot mix inclusion and comparison operators.")
        return in_ops
    if compare_ops:
        return compare_ops
    raise ValidationError(f"{field} must contain at least one operator.")


def coerce_where(value: JSONValue, field: str) -> Where:
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be a JSON object.")
    out: Where = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key:
            raise ValidationError(f"{field} contains an invalid key.")
        if raw_key in {"$and", "$or"}:
            if not isinstance(raw_value, list):
                raise ValidationError(f"{field}.{raw_key} must be a list of where clauses.")
            clauses: list[Where] = []
            for item in raw_value:
                clauses.append(coerce_where(item, f"{field}.{raw_key}"))
            out[raw_key] = clauses
            continue
        if isinstance(raw_value, dict):
            out[raw_key] = coerce_operator_expression(raw_value, f"{field}.{raw_key}")
            continue
        if isinstance(raw_value, list):
            raise ValidationError(f"{field}.{raw_key} must be a literal value or operator object.")
        out[raw_key] = coerce_literal_value(raw_value, f"{field}.{raw_key}")
    return out


def coerce_str_list(value: JSONValue, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"{field} must be a list of strings.")
    return [item for item in value if isinstance(item, str)]


def coerce_include(value: JSONValue, field: str) -> Include:
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be a list.")
    include: Include = []
    for raw_item in value:
        if not isinstance(raw_item, str):
            raise ValidationError(f"{field} must contain only strings.")
        match raw_item:
            case "documents":
                include.append("documents")
            case "embeddings":
                include.append("embeddings")
            case "metadatas":
                include.append("metadatas")
            case "distances":
                include.append("distances")
            case "uris":
                include.append("uris")
            case "data":
                include.append("data")
            case _:
                raise ValidationError(f"{field} contains an invalid include entry: {raw_item}")
    return include


def coerce_py_embedding_vector(value: JSONValue, field: str) -> PyEmbedding:
    if not isinstance(value, list):
        raise ValidationError(f"{field} embedding vector must be a list.")
    out: list[float] = []
    for item in value:
        if (
            isinstance(item, bool)
            or not isinstance(item, int | float)
            or not math.isfinite(float(item))
        ):
            raise ValidationError(f"{field} embedding vector contains a non-numeric value.")
        out.append(float(item))
    return out


def coerce_py_embeddings_list(value: JSONValue, field: str) -> list[PyEmbedding]:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{field} must be a non-empty list.")
    out: list[PyEmbedding] = []
    for index, item in enumerate(value):
        out.append(coerce_py_embedding_vector(item, f"{field}[{index}]"))
    return out


def coerce_query_embeddings(value: JSONValue, field: str) -> PyEmbedding | list[PyEmbedding]:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{field} must be a non-empty list.")
    if isinstance(value[0], list):
        return coerce_py_embeddings_list(value, field)
    return coerce_py_embedding_vector(value, field)


def coerce_metadata_list(value: JSONValue, field: str) -> list[Metadata]:
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be a list of JSON objects.")
    out: list[Metadata] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValidationError(f"{field}[{index}] must be a JSON object.")
        metadata: dict[str, str | int | float | bool | None] = {}
        for key, meta_value in item.items():
            if not isinstance(key, str) or not key:
                raise ValidationError(f"{field}[{index}] contains an invalid metadata key.")
            if meta_value is None:
                metadata[key] = None
                continue
            if isinstance(meta_value, bool):
                metadata[key] = meta_value
                continue
            if is_strict_int(meta_value):
                metadata[key] = meta_value
                continue
            if (
                isinstance(meta_value, float)
                and not isinstance(meta_value, bool)
                and math.isfinite(meta_value)
            ):
                metadata[key] = meta_value
                continue
            if isinstance(meta_value, str):
                metadata[key] = meta_value
                continue
            raise ValidationError(f"{field}[{index}].{key} must be a scalar value or null.")
        out.append(metadata)
    return out


def coerce_payload_int(
    payload: dict[str, JSONValue],
    field: str,
    *,
    default: int,
) -> int:
    value = payload.get(field)
    if value is None:
        return int(default)
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer.")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return int(value)
        raise ValidationError(f"{field} must be an integer.")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
        raise ValidationError(f"{field} must be an integer.")
    raise ValidationError(f"{field} must be an integer.")

"""SoAI - Chroma IPC result normalization [backend/mcp/storage/chroma_json_results.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from chromadb.api.types import GetResult, QueryResult
from chromadb.base_types import SparseVector
from numpy import bool_, floating, integer, ndarray

from core.serialization.json import normalize_for_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

    type ChromaJsonValue = (
        None
        | bool
        | int
        | float
        | str
        | bool_
        | floating
        | integer
        | ndarray
        | SparseVector
        | Mapping[str, ChromaJsonValue]
        | Sequence[ChromaJsonValue]
    )

__all__ = (
    "normalize_chroma_get_result",
    "normalize_chroma_query_result",
)


def _normalize_numeric_ndarray(value: ndarray) -> JSONValue:
    if value.ndim <= 1:
        return [float(value.item(index)) for index in range(int(value.size))]
    return [_normalize_numeric_ndarray(value[index]) for index in range(int(value.shape[0]))]


def _normalize_chroma_value(value: ChromaJsonValue) -> JSONValue:
    if value is None:
        return None
    if isinstance(value, ndarray):
        return _normalize_numeric_ndarray(value)
    if isinstance(value, bool_):
        return bool(value)
    if isinstance(value, integer):
        return int(value)
    if isinstance(value, floating):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _normalize_chroma_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_normalize_chroma_value(item) for item in value]
    return normalize_for_json(value)


def _normalize_chroma_result_base(value: GetResult | QueryResult) -> JSONDict:
    result: JSONDict = {
        "ids": normalize_for_json(value["ids"]),
        "included": normalize_for_json(value["included"]),
    }
    documents = value.get("documents")
    if documents is not None:
        result["documents"] = normalize_for_json(documents)
    uris = value.get("uris")
    if uris is not None:
        result["uris"] = normalize_for_json(uris)
    metadatas = value.get("metadatas")
    if metadatas is not None:
        result["metadatas"] = _normalize_chroma_value(metadatas)
    embeddings = value.get("embeddings")
    if embeddings is not None:
        result["embeddings"] = _normalize_chroma_value(embeddings)
    data = value.get("data")
    if data is not None:
        result["data"] = _normalize_chroma_value(data)
    return result


def normalize_chroma_get_result(value: GetResult) -> JSONDict:
    return _normalize_chroma_result_base(value)


def normalize_chroma_query_result(value: QueryResult) -> JSONDict:
    result = _normalize_chroma_result_base(value)
    distances = value["distances"]
    if distances is not None:
        result["distances"] = normalize_for_json(distances)
    return result

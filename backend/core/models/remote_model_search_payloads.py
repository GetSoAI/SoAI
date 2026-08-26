"""SoAI - Remote model search payload serialization [backend/core/models/remote_model_search_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.models.remote_model_search_types import (
    RemoteModelSearchResult,
    RemoteModelSearchVariant,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "normalize_model_search_payload",
    "serialize_search_result",
    "serialize_search_variant",
)


def serialize_search_variant(variant: RemoteModelSearchVariant) -> JSONDict:
    payload: JSONDict = {"id": variant.id, "name": variant.name, "uri": variant.uri}
    if variant.size_bytes is not None:
        payload["size_bytes"] = variant.size_bytes
    if variant.quantization:
        payload["quantization"] = variant.quantization
    if variant.checksum:
        payload["checksum"] = variant.checksum
    if variant.extra:
        payload["extra"] = variant.extra
    return payload


def serialize_search_result(result: RemoteModelSearchResult) -> JSONDict:
    payload: JSONDict = {
        "id": result.id,
        "name": result.name,
        "source": result.source,
        "variants": [serialize_search_variant(variant) for variant in result.variants],
    }
    if result.summary:
        payload["summary"] = result.summary
    if result.score is not None:
        payload["score"] = result.score
    if result.tags:
        payload["tags"] = list(result.tags)
    if result.metadata:
        payload["metadata"] = result.metadata
    return payload


def normalize_model_search_payload(
    results: Sequence[RemoteModelSearchResult | JSONDict],
) -> list[JSONDict]:
    normalized: list[JSONDict] = []
    if not results:
        return normalized
    for entry in results:
        if isinstance(entry, RemoteModelSearchResult):
            normalized.append(serialize_search_result(entry))
        elif isinstance(entry, dict):
            normalized.append(entry)
    return normalized

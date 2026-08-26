"""SoAI - Linked knowledge retrieval augmentation [backend/mcp/rag/linked_retrieval.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.types.json import is_json_dict
from mcp.rag.linked_strategy_queries import (
    LinkedDocumentQuery,
    LinkedRetrievalParameters,
    query_linked_documents,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = ("LinkedKnowledgeAugmentRequest", "augment_results_with_linked_knowledge")


@dataclass(frozen=True, slots=True)
class LinkedKnowledgeAugmentRequest:
    conv_id: str
    user_id: int
    parameters: LinkedRetrievalParameters


def _group_linked_documents(
    linked_documents: list[dict[str, str | int]],
) -> dict[tuple[str, int], set[str]]:
    grouped: dict[tuple[str, int], set[str]] = {}
    for linked_document in linked_documents:
        source_conv_id = linked_document.get("source_conv_id")
        source_user_id = linked_document.get("source_user_id")
        source_document_id = linked_document.get("source_document_id")
        if (
            isinstance(source_conv_id, str)
            and isinstance(source_user_id, int)
            and isinstance(source_document_id, str)
        ):
            key = (source_conv_id, source_user_id)
            if key not in grouped:
                grouped[key] = set()
            grouped[key].add(source_document_id)
    return grouped


def _result_key(result: JSONDict, *, fallback_conv_id: str) -> tuple[str, str, int]:
    source_conv_id = result.get("source_conv_id")
    document_id = result.get("document_id")
    chunk_index = result.get("chunk_index")
    resolved_source_conv_id = (
        source_conv_id if isinstance(source_conv_id, str) else fallback_conv_id
    )
    resolved_document_id = document_id if isinstance(document_id, str) else ""
    resolved_chunk_index = chunk_index if isinstance(chunk_index, int) else 0
    return (resolved_source_conv_id, resolved_document_id, resolved_chunk_index)


def _result_similarity(result: JSONDict) -> float:
    value = result.get("similarity")
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _result_chunk_index(result: JSONDict) -> int:
    value = result.get("chunk_index")
    if isinstance(value, int):
        return value
    return 0


def _merge_results(
    *,
    conv_id: str,
    native_results: list[JSONDict],
    linked_results: list[JSONDict],
    top_k: int,
) -> list[JSONDict]:
    merged: list[JSONDict] = []
    seen: set[tuple[str, str, int]] = set()
    for result in (*native_results, *linked_results):
        key = _result_key(result, fallback_conv_id=conv_id)
        if key in seen:
            continue
        seen.add(key)
        merged.append(result)
    merged.sort(
        key=lambda result: (
            -_result_similarity(result),
            str(result.get("source_conv_id") or conv_id),
            str(result.get("document_id") or ""),
            _result_chunk_index(result),
        ),
    )
    return merged[:top_k]


async def _collect_linked_results(
    *,
    rag: MCPRAGInternalProtocol,
    grouped: dict[tuple[str, int], set[str]],
    request: LinkedKnowledgeAugmentRequest,
) -> list[JSONDict]:
    linked_results: list[JSONDict] = []
    for (source_conv_id, source_user_id), document_ids in grouped.items():
        query_request = LinkedDocumentQuery(
            source_user_id=source_user_id,
            document_ids=document_ids,
            parameters=request.parameters,
        )
        linked_results.extend(
            await query_linked_documents(
                rag=rag,
                source_conv_id=source_conv_id,
                request=query_request,
            ),
        )
    return linked_results


async def augment_results_with_linked_knowledge(
    *,
    rag: MCPRAGInternalProtocol,
    request: LinkedKnowledgeAugmentRequest,
    native_result: JSONDict,
) -> JSONDict:
    if request.user_id <= 0:
        return native_result
    linked_documents = await rag.database_files.get_active_linked_rag_documents(
        request.conv_id,
        request.user_id,
    )
    grouped = _group_linked_documents(linked_documents)
    if not grouped:
        return native_result
    linked_results = await _collect_linked_results(
        rag=rag,
        grouped=grouped,
        request=request,
    )
    raw_native_results = native_result.get("results")
    native_results = raw_native_results if isinstance(raw_native_results, list) else []
    merged_results = [result for result in native_results if is_json_dict(result)]
    final_results = _merge_results(
        conv_id=request.conv_id,
        native_results=merged_results,
        linked_results=linked_results,
        top_k=request.parameters.top_k,
    )
    result = dict(native_result)
    result["results"] = final_results
    result["count"] = len(final_results)
    return result

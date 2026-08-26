"""SoAI - Web-fetch ingest immediate context limits and shaping [backend/mcp/worker/processors/web_fetch_ingest_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.config.numeric import require_strict_int_at_least
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "FetchContextLimits",
    "build_bounded_immediate_context",
    "resolve_fetch_context_limits",
)

_FETCH_CONTEXT_MAX_TOP_K_KEY = "TOOLS.RAG.WEB.FETCH_CONTEXT.MAX_TOP_K"
_FETCH_CONTEXT_MAX_PASSAGE_CHARS_KEY = "TOOLS.RAG.WEB.FETCH_CONTEXT.MAX_PASSAGE_CHARS"
_FETCH_CONTEXT_MAX_TOTAL_CHARS_KEY = "TOOLS.RAG.WEB.FETCH_CONTEXT.MAX_TOTAL_CHARS"
_IMMEDIATE_CONTEXT_STRING_FIELDS = ("document_id", "source_type", "source_url")


@functools.cache
def _whitespace_runs_pattern() -> re.Pattern[str]:
    return re.compile("[ \\t\\f\\v]+")


@functools.cache
def _newline_runs_pattern() -> re.Pattern[str]:
    return re.compile("\\n{3,}")


@dataclass(frozen=True, slots=True)
class FetchContextLimits:
    max_top_k: int
    max_passage_chars: int
    max_total_chars: int


def resolve_fetch_context_limits(worker: MCPWorkerProtocol) -> FetchContextLimits:
    max_top_k = require_strict_int_at_least(
        worker.config.get_int(_FETCH_CONTEXT_MAX_TOP_K_KEY),
        key=_FETCH_CONTEXT_MAX_TOP_K_KEY,
        minimum=1,
    )
    max_passage_chars = require_strict_int_at_least(
        worker.config.get_int(_FETCH_CONTEXT_MAX_PASSAGE_CHARS_KEY),
        key=_FETCH_CONTEXT_MAX_PASSAGE_CHARS_KEY,
        minimum=1,
    )
    max_total_chars = require_strict_int_at_least(
        worker.config.get_int(_FETCH_CONTEXT_MAX_TOTAL_CHARS_KEY),
        key=_FETCH_CONTEXT_MAX_TOTAL_CHARS_KEY,
        minimum=1,
    )
    return FetchContextLimits(
        max_top_k=max_top_k,
        max_passage_chars=max_passage_chars,
        max_total_chars=max_total_chars,
    )


def _normalize_immediate_context_content(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _whitespace_runs_pattern().sub(" ", normalized)
    normalized = _newline_runs_pattern().sub("\n\n", normalized)
    return normalized.strip()


def truncate_at_boundary(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    candidate = content[:max_chars]
    boundary_candidates = (
        candidate.rfind("\n\n"),
        candidate.rfind("\n"),
        candidate.rfind(". "),
        candidate.rfind("! "),
        candidate.rfind("? "),
    )
    best_boundary = max(boundary_candidates)
    minimum_boundary = int(max_chars * 0.6)
    if best_boundary >= minimum_boundary:
        if candidate[best_boundary : best_boundary + 2] in {". ", "! ", "? "}:
            return candidate[: best_boundary + 1].rstrip()
        return candidate[:best_boundary].rstrip()
    return candidate.rstrip()


def _content_fingerprint(content: str) -> str:
    normalized = re.sub("[^a-z0-9]+", " ", content.lower()).strip()
    return normalized[:160]


def build_bounded_immediate_context(
    *,
    limits: FetchContextLimits,
    query: str,
    retrieval_strategy: str,
    search_result: JSONDict,
) -> tuple[JSONDict, JSONDict]:
    raw_results_value = search_result.get("results")
    raw_results = (
        [item for item in raw_results_value if isinstance(item, dict)]
        if isinstance(raw_results_value, list)
        else []
    )
    considered_results = raw_results[: limits.max_top_k]
    bounded_results: list[JSONDict] = []
    total_chars = 0
    truncated = len(raw_results) > len(considered_results)
    fingerprints_seen: set[str] = set()
    for item in considered_results:
        content_raw = item.get("content")
        if not isinstance(content_raw, str):
            continue
        bounded_content = _normalize_immediate_context_content(content_raw)
        if not bounded_content:
            continue
        if len(bounded_content) > limits.max_passage_chars:
            bounded_content = truncate_at_boundary(bounded_content, limits.max_passage_chars)
            truncated = True
        remaining = limits.max_total_chars - total_chars
        if remaining <= 0:
            truncated = True
            break
        if len(bounded_content) > remaining:
            bounded_content = truncate_at_boundary(bounded_content, remaining)
            truncated = True
        if not bounded_content:
            continue
        fingerprint = _content_fingerprint(bounded_content)
        if fingerprint and fingerprint in fingerprints_seen:
            truncated = True
            continue
        if fingerprint:
            fingerprints_seen.add(fingerprint)
        total_chars += len(bounded_content)
        bounded_item: JSONDict = {"content": bounded_content}
        similarity_value = item.get("similarity")
        if isinstance(similarity_value, int | float) and not isinstance(similarity_value, bool):
            normalized_similarity = float(similarity_value)
            if math.isfinite(normalized_similarity):
                bounded_item["similarity"] = normalized_similarity
        chunk_index_value = item.get("chunk_index")
        if is_strict_int(chunk_index_value):
            bounded_item["chunk_index"] = chunk_index_value
        for field_name in _IMMEDIATE_CONTEXT_STRING_FIELDS:
            field_value = item.get(field_name)
            if isinstance(field_value, str) and field_value:
                bounded_item[field_name] = field_value
        bounded_results.append(bounded_item)
    immediate_context: JSONDict = {
        "query": query,
        "retrieval_strategy": retrieval_strategy,
        "count": len(bounded_results),
        "results": bounded_results,
    }
    output_limits: JSONDict = {
        "max_passage_chars": limits.max_passage_chars,
        "max_total_chars": limits.max_total_chars,
        "truncated": truncated,
    }
    return (immediate_context, output_limits)

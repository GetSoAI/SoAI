"""SoAI - Installed documentation deterministic relevance ranking [backend/core/documentation/relevance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.documentation.bundle_parsing import DocumentationRecord
from core.documentation.search_index import DocumentationSearchIndex
from core.documentation.tokenization import DocumentationQueryGroup, build_query_groups

__all__ = (
    "DocumentationSearchMatches",
    "DocumentationSearchResult",
    "search_documentation_index",
)

_BM25_K1 = 1.2
_BM25_B = 0.75


@dataclass(frozen=True, slots=True)
class DocumentationSearchResult:
    record: DocumentationRecord
    score: float
    query_surfaces: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentationSearchMatches:
    normalized_query: str
    total_matches: int
    results: tuple[DocumentationSearchResult, ...]


def _is_edit_distance_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(first != second for first, second in zip(left, right, strict=True)) == 1
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    short_index = 0
    long_index = 0
    skipped = False
    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
            continue
        if skipped:
            return False
        skipped = True
        long_index += 1
    return True


def _expanded_terms(
    group: DocumentationQueryGroup,
    index: DocumentationSearchIndex,
) -> tuple[tuple[str, float], ...]:
    exact = tuple(term for term in group.variants if term in index.postings)
    if exact:
        return tuple((term, 1.0) for term in exact)
    surface = group.surface
    prefixes = (
        tuple(term for term in index.vocabulary if term.startswith(surface))
        if len(surface) >= 4
        else ()
    )
    candidates = prefixes
    discount = 0.6
    if not candidates:
        candidates = tuple(
            term
            for term in index.vocabulary
            if abs(len(term) - len(surface)) <= 1 and _is_edit_distance_one(surface, term)
        )
        discount = 0.45
    ranked = sorted(
        candidates,
        key=lambda term: (-index.document_frequencies[term], term),
    )[:4]
    return tuple((term, discount) for term in ranked)


def _term_scores(
    term: str,
    discount: float,
    index: DocumentationSearchIndex,
) -> dict[int, float]:
    scores: dict[int, float] = {}
    inverse_document_frequency = index.inverse_document_frequencies[term]
    for record_index, frequency in index.postings[term]:
        length_ratio = index.record_lengths[record_index] / index.average_record_length
        denominator = frequency + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * length_ratio)
        scores[record_index] = (
            inverse_document_frequency * (frequency * (_BM25_K1 + 1.0) / denominator) * discount
        )
    return scores


def search_documentation_index(
    index: DocumentationSearchIndex,
    *,
    query: str,
    max_results: int,
) -> DocumentationSearchMatches:
    groups = build_query_groups(query)
    totals: dict[int, float] = {}
    coverage: dict[int, int] = {}
    for group in groups:
        best_for_group: dict[int, float] = {}
        for term, discount in _expanded_terms(group, index):
            for record_index, score in _term_scores(term, discount, index).items():
                best_for_group[record_index] = max(best_for_group.get(record_index, 0.0), score)
        for record_index, score in best_for_group.items():
            totals[record_index] = totals.get(record_index, 0.0) + score
            coverage[record_index] = coverage.get(record_index, 0) + 1
    ranked = sorted(
        (
            DocumentationSearchResult(
                record=index.corpus.records[record_index],
                score=score * (0.3 + 0.7 * coverage[record_index] / len(groups)),
                query_surfaces=tuple(group.surface for group in groups),
            )
            for record_index, score in totals.items()
        ),
        key=lambda result: (
            -result.score,
            result.record.page_id,
            result.record.start_offset,
            result.record.identity,
        ),
    )
    capped: list[DocumentationSearchResult] = []
    page_counts: dict[str, int] = {}
    for result in ranked:
        page_count = page_counts.get(result.record.page_id, 0)
        if page_count >= 2:
            continue
        page_counts[result.record.page_id] = page_count + 1
        capped.append(result)
    return DocumentationSearchMatches(
        normalized_query=" ".join(group.surface for group in groups),
        total_matches=len(capped),
        results=tuple(capped[:max_results]),
    )

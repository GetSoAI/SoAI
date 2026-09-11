"""SoAI - Installed documentation immutable lexical index [backend/core/documentation/search_index.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from types import MappingProxyType

from core.concurrency.singleflight import ResultCopyMode, SyncSingleflight
from core.documentation.bundle_parsing import DocumentationCorpus, parse_documentation_bundle
from core.documentation.tokenization import tokenize_documentation_text
from core.errors.exceptions import ValidationError

__all__ = (
    "DocumentationSearchIndex",
    "build_documentation_search_index",
)

_FIELD_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("page_title", 4.0),
    ("page_id", 3.0),
    ("heading_path", 3.0),
    ("section", 2.0),
    ("body", 1.0),
)
_DOCUMENTATION_INDEX_FLIGHT_KEY = "installed-documentation"


@dataclass(frozen=True, slots=True)
class DocumentationSearchIndex:
    corpus: DocumentationCorpus
    postings: MappingProxyType[str, tuple[tuple[int, float], ...]]
    document_frequencies: MappingProxyType[str, int]
    inverse_document_frequencies: MappingProxyType[str, float]
    record_lengths: tuple[float, ...]
    average_record_length: float
    vocabulary: tuple[str, ...]


def _field_text(record_index: int, corpus: DocumentationCorpus, field: str) -> str:
    record = corpus.records[record_index]
    if field == "page_title":
        return record.page_title
    if field == "page_id":
        return record.page_id
    if field == "heading_path":
        return " ".join(record.heading_path)
    if field == "section":
        return record.section
    return record.body


def _build_index(corpus: DocumentationCorpus) -> DocumentationSearchIndex:
    if not corpus.records:
        raise ValidationError("Documentation bundle contains no searchable records")
    posting_maps: dict[str, dict[int, float]] = {}
    record_lengths: list[float] = []
    for record_index in range(len(corpus.records)):
        weighted_length = 0.0
        for field, weight in _FIELD_WEIGHTS:
            token_groups = tokenize_documentation_text(_field_text(record_index, corpus, field))
            weighted_length += len(token_groups) * weight
            for group in token_groups:
                for term in frozenset(group):
                    if term not in posting_maps:
                        posting_maps[term] = {}
                    postings = posting_maps[term]
                    postings[record_index] = postings.get(record_index, 0.0) + weight
        record_lengths.append(weighted_length)
    average_length = sum(record_lengths) / len(record_lengths)
    if average_length <= 0:
        raise ValidationError("Documentation searchable records contain no lexical terms")
    document_frequencies = {term: len(postings) for term, postings in posting_maps.items()}
    record_count = len(corpus.records)
    inverse_document_frequencies = {
        term: math.log(1.0 + (record_count - frequency + 0.5) / (frequency + 0.5))
        for term, frequency in document_frequencies.items()
    }
    immutable_postings = MappingProxyType(
        {term: tuple(sorted(values.items())) for term, values in posting_maps.items()}
    )
    return DocumentationSearchIndex(
        corpus=corpus,
        postings=immutable_postings,
        document_frequencies=MappingProxyType(document_frequencies),
        inverse_document_frequencies=MappingProxyType(inverse_document_frequencies),
        record_lengths=tuple(record_lengths),
        average_record_length=average_length,
        vocabulary=tuple(sorted(posting_maps)),
    )


def _load_documentation_search_index() -> DocumentationSearchIndex:
    source = (
        resources.files("core.documentation.assets")
        .joinpath("soai_documentation.md")
        .read_text("utf-8")
    )
    return _build_index(parse_documentation_bundle(source))


@lru_cache(maxsize=1)
def _documentation_index_singleflight() -> SyncSingleflight[str, DocumentationSearchIndex]:
    return SyncSingleflight(result_copier=ResultCopyMode.NONE)


@lru_cache(maxsize=1)
def build_documentation_search_index() -> DocumentationSearchIndex:
    return _documentation_index_singleflight().execute_or_wait(
        _DOCUMENTATION_INDEX_FLIGHT_KEY,
        _load_documentation_search_index,
    )

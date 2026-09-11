"""SoAI - Installed documentation lexical tokenization [backend/core/documentation/tokenization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.rag.bm25_options import BM25_EN_STOPWORDS

__all__ = (
    "DocumentationQueryGroup",
    "build_query_groups",
    "tokenize_documentation_text",
)

_TOKEN_PATTERN = r"[a-z0-9][a-z0-9_.\-]*"
_TRAILING_SEPARATORS = "._-"
_MAX_QUERY_CHARACTERS = 4096
_MAX_QUERY_TERMS = 32


@dataclass(frozen=True, slots=True)
class DocumentationQueryGroup:
    surface: str
    variants: tuple[str, ...]


def _fold_suffix(token: str) -> str | None:
    for suffix, replacement in (
        ("ies", "y"),
        ("sses", "ss"),
        ("ing", ""),
        ("ed", ""),
        ("es", ""),
        ("ly", ""),
        ("s", ""),
    ):
        if token.endswith(suffix):
            folded = token[: -len(suffix)] + replacement
            if len(folded) >= 4:
                return folded
    return None


def _normalized_surface_tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(
        token.rstrip(_TRAILING_SEPARATORS)
        for token in re.findall(_TOKEN_PATTERN, normalized)
        if token.rstrip(_TRAILING_SEPARATORS)
    )


def _variants(surface: str) -> tuple[str, ...]:
    values: list[str] = [surface]
    if any(separator in surface for separator in "._-"):
        values.extend(part for part in re.split(r"[._-]+", surface) if part)
    for value in tuple(values):
        folded = _fold_suffix(value)
        if folded is not None:
            values.append(folded)
    return tuple(dict.fromkeys(values))


def tokenize_documentation_text(text: str) -> tuple[tuple[str, ...], ...]:
    return tuple(_variants(surface) for surface in _normalized_surface_tokens(text))


def build_query_groups(query: str) -> tuple[DocumentationQueryGroup, ...]:
    if len(query) > _MAX_QUERY_CHARACTERS:
        raise ValidationError("query must be <= 4096 characters")
    surfaces = tuple(dict.fromkeys(_normalized_surface_tokens(query)))
    if not surfaces:
        raise ValidationError("query must contain an English word or exact identifier")
    if len(surfaces) > _MAX_QUERY_TERMS:
        raise ValidationError("query must contain no more than 32 distinct searchable terms")
    filtered = tuple(surface for surface in surfaces if surface not in BM25_EN_STOPWORDS)
    selected = filtered or surfaces
    return tuple(
        DocumentationQueryGroup(surface=surface, variants=_variants(surface))
        for surface in selected
    )

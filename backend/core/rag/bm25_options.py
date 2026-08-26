"""SoAI - BM25 option constants [backend/core/rag/bm25_options.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "BM25_EN_STOPWORDS",
    "BM25_STOPWORD_MODES",
    "BM25_TOKENIZERS",
    "DEFAULT_BM25_STOPWORDS_MODE",
    "DEFAULT_BM25_TOKENIZER",
)

DEFAULT_BM25_TOKENIZER = "unicode61"
DEFAULT_BM25_STOPWORDS_MODE = "none"
BM25_TOKENIZERS: frozenset[str] = frozenset(("unicode61", "porter", "trigram"))
BM25_STOPWORD_MODES: frozenset[str] = frozenset(("none", "en"))
BM25_EN_STOPWORDS: frozenset[str] = frozenset(
    (
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "has",
        "have",
        "he",
        "her",
        "his",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "no",
        "not",
        "of",
        "on",
        "or",
        "our",
        "she",
        "so",
        "that",
        "the",
        "their",
        "them",
        "they",
        "this",
        "to",
        "up",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
    ),
)

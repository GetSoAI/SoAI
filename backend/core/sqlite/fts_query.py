"""SoAI - SQLite FTS query normalization [backend/core/sqlite/fts_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

__all__ = ("build_fts_prefix_match_query",)


def build_fts_prefix_match_query(
    query: str,
    *,
    max_terms: int = 8,
    column: str | None = None,
) -> str:
    terms: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"[^\W_]+", query.lower()):
        term = match.group(0)
        if term in seen:
            continue
        terms.append(f"{term}*")
        seen.add(term)
        if len(terms) >= max_terms:
            break
    match_query = " AND ".join(terms)
    if not match_query or column is None:
        return match_query
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", column):
        raise ValueError("SQLite FTS column name is invalid.")
    return f"{column} : ({match_query})"

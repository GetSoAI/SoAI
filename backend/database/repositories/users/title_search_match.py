"""SoAI - User title search FTS match construction [backend/database/repositories/users/title_search_match.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.sqlite.fts_query import build_fts_prefix_match_query

__all__ = ("build_user_title_search_match",)


def build_user_title_search_match(user_id: int, query: str, title_column: str) -> str:
    if user_id <= 0:
        return ""
    title_query = build_fts_prefix_match_query(query, column=title_column)
    if not title_query:
        return ""
    return f"owner_key : u{user_id} AND {title_query}"

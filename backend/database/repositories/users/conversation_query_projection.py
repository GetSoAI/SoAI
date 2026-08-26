"""SoAI - Canonical conversation row query projection [backend/database/repositories/users/conversation_query_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from database.repositories.users.conversation_compaction_metrics import (
    CONVERSATION_COMPACTION_METRICS_JOIN_SQL,
    CONVERSATION_COMPACTION_METRICS_SELECT_SQL,
)
from database.repositories.users.messaging_conversation_projection import (
    MESSAGING_CONVERSATION_AUTHORITY_JOIN_SQL,
    MESSAGING_CONVERSATION_AUTHORITY_SELECT_SQL,
)

__all__ = (
    "conversation_query_joins_sql",
    "conversation_query_select_sql",
)


def conversation_query_select_sql() -> str:
    return f"""
    {CONVERSATION_COMPACTION_METRICS_SELECT_SQL},
    {MESSAGING_CONVERSATION_AUTHORITY_SELECT_SQL}
    """


def conversation_query_joins_sql() -> str:
    return f"""
    {CONVERSATION_COMPACTION_METRICS_JOIN_SQL}
    {MESSAGING_CONVERSATION_AUTHORITY_JOIN_SQL}
    """

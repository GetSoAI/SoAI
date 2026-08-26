"""SoAI - Conversation compaction metric SQL fragments [backend/database/repositories/users/conversation_compaction_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "CONVERSATION_COMPACTION_METRICS_JOIN_SQL",
    "CONVERSATION_COMPACTION_METRICS_SELECT_SQL",
)

CONVERSATION_COMPACTION_METRICS_SELECT_SQL = """
    COALESCE(compaction_metrics.compaction_count, 0) AS compaction_count,
    COALESCE(compaction_metrics.compaction_tokens_saved, 0) AS compaction_tokens_saved
"""

CONVERSATION_COMPACTION_METRICS_JOIN_SQL = """
LEFT JOIN (
    SELECT
        conv_id,
        COALESCE(
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END),
            0
        ) AS compaction_count,
        COALESCE(SUM(tokens_saved), 0) AS compaction_tokens_saved
    FROM webui_context_compaction_metric_events
    GROUP BY conv_id
) AS compaction_metrics
  ON compaction_metrics.conv_id = c.id
"""

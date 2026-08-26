"""SoAI - Automation occurrence deletion queries [backend/database/repositories/users/automation_occurrence_deletion_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.automation.automation_constants import AUTOMATION_OCCURRENCES_MAX_ITEMS
from core.database.protocols import DatabaseCoreProtocol
from core.validation.integers import is_strict_int
from database.core.flags import FEATURE_PROMPTS
from database.core.query_execution import query_to_dicts

__all__ = ("list_occurrence_deletion_keys_for_window",)


async def list_occurrence_deletion_keys_for_window(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    from_utc_ms: int,
    to_utc_ms: int,
) -> set[tuple[str, int]]:
    core.features.ensure_feature_enabled(FEATURE_PROMPTS)

    async def _query(database: aiosqlite.Connection) -> set[tuple[str, int]]:
        rows = await query_to_dicts(
            database,
            """
            SELECT d.automation_id, d.scheduled_at_ms AS scheduled_at_ms
            FROM automation_occurrence_deletions AS d
            JOIN automations AS a
                ON a.id = d.automation_id AND a.user_id = d.user_id
            WHERE d.user_id = ?
                AND a.enabled = 1
                AND d.scheduled_at_ms >= ?
                AND d.scheduled_at_ms < ?
            ORDER BY d.scheduled_at_ms ASC, d.automation_id ASC
            LIMIT ?
            """,
            (user_id, from_utc_ms, to_utc_ms, AUTOMATION_OCCURRENCES_MAX_ITEMS),
        )
        deleted: set[tuple[str, int]] = set()
        for row in rows:
            automation_id = row.get("automation_id")
            scheduled_at_ms = row.get("scheduled_at_ms")
            if not isinstance(automation_id, str) or not automation_id.strip():
                continue
            if not is_strict_int(scheduled_at_ms):
                continue
            deleted.add((automation_id.strip(), scheduled_at_ms))
        return deleted

    return await core.reader.execute_read(_query)

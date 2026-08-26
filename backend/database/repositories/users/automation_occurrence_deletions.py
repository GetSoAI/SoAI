"""SoAI - Automation occurrence deletion repository [backend/database/repositories/users/automation_occurrence_deletions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.automation_occurrence_deletion_operations import (
    should_notify_for_occurrence_deletion_result,
    sync_delete_automation_occurrences,
)
from database.repositories.users.automation_occurrence_deletion_queries import (
    list_occurrence_deletion_keys_for_window,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAutomationOccurrenceDeletions",)


class DatabaseAutomationOccurrenceDeletions:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core

    async def list_occurrence_deletions_for_window(
        self,
        user_id: int,
        *,
        from_utc_ms: int,
        to_utc_ms: int,
    ) -> set[tuple[str, int]]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_occurrence_deletion_keys_for_window(
            self.core,
            user_id=user_id,
            from_utc_ms=from_utc_ms,
            to_utc_ms=to_utc_ms,
        )

    async def delete_occurrences(
        self,
        user_id: int,
        *,
        occurrences: list[tuple[str, int]],
        deleted_at_ms: int,
    ) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            sync_delete_automation_occurrences,
            user_id,
            occurrences,
            deleted_at_ms,
        )
        if should_notify_for_occurrence_deletion_result(result):
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

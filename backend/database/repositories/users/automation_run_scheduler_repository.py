"""SoAI - Automation run scheduler repository [backend/database/repositories/users/automation_run_scheduler_repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.automation_run_scheduler_queries import (
    count_active_automation_runs_by_user,
    list_queued_automation_run_ids,
    list_running_automation_run_summaries,
)
from database.repositories.users.automation_run_state_commits import (
    mark_restarted_running_automation_runs,
)

if TYPE_CHECKING:
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAutomationRunScheduler",)


class DatabaseAutomationRunScheduler:
    def __init__(
        self,
        deps: DatabaseRepositoryDependencies,
        database_notifications: DatabaseNotificationsProtocol,
    ) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config
        self._database_notifications = database_notifications

    async def count_active_runs_by_user(self) -> dict[int, int]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await count_active_automation_runs_by_user(self.core)

    async def mark_restarted_running_runs(
        self,
        *,
        now_ms: int,
        status_message: str,
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await mark_restarted_running_automation_runs(
            self._deps,
            self._database_notifications,
            self.config,
            now_ms=now_ms,
            status_message=status_message,
        )

    async def list_queued_run_ids(self) -> list[str]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_queued_automation_run_ids(self.core)

    async def list_running_run_summaries(self, *, limit: int) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_running_automation_run_summaries(self.core, limit=limit)

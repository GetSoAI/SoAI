"""SoAI - Automation run repository [backend/database/repositories/users/automation_runs/repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.automation_run_creation import sync_create_run_now
from database.repositories.users.automation_run_read_queries import (
    get_automation_run,
    get_automation_run_for_execution,
    list_active_automation_run_ids_for_conversation,
    list_active_automation_runs,
    list_automation_run_window_records,
    list_automation_runs,
)
from database.repositories.users.automation_run_state_commits import (
    complete_automation_run_abandoned,
    complete_automation_run_cancelled,
    complete_automation_run_completed,
    complete_automation_run_error,
)
from database.repositories.users.automation_run_transitions import (
    sync_attach_run_conversation,
    sync_attach_run_owner_task_id,
    sync_mark_run_running,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAutomationRuns",)


class DatabaseAutomationRuns:
    def __init__(
        self,
        deps: DatabaseRepositoryDependencies,
        database_notifications: DatabaseNotificationsProtocol,
    ) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config
        self._database_notifications = database_notifications

    async def get_run(self, run_id: str, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await get_automation_run(self.core, run_id=run_id, user_id=user_id)

    async def list_active_runs(self, user_id: int) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_active_automation_runs(self.core, user_id=user_id)

    async def list_active_run_ids_for_conversation(
        self,
        user_id: int,
        *,
        conv_id: str,
    ) -> list[str]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_active_automation_run_ids_for_conversation(
            self.core,
            user_id=user_id,
            conv_id=conv_id,
        )

    async def list_runs(
        self,
        user_id: int,
        *,
        from_utc_ms: int,
        to_utc_ms: int,
        automation_id: str | None,
        limit: int,
        offset: int,
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_automation_runs(
            self.core,
            user_id=user_id,
            from_utc_ms=from_utc_ms,
            to_utc_ms=to_utc_ms,
            automation_id=automation_id,
            limit=limit,
            offset=offset,
        )

    async def create_run_now(self, automation_id: str, user_id: int, now_ms: int) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            sync_create_run_now,
            automation_id,
            user_id,
            now_ms,
        )
        notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def mark_run_running(self, run_id: str, *, now_ms: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            sync_mark_run_running,
            run_id,
            now_ms,
        )
        if isinstance(result, dict):
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def attach_conversation(
        self,
        run_id: str,
        user_id: int,
        conv_id: str,
        *,
        now_ms: int,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            sync_attach_run_conversation,
            run_id,
            user_id,
            conv_id,
            now_ms,
        )
        if isinstance(result, dict):
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def attach_owner_task_id(
        self,
        run_id: str,
        user_id: int,
        owner_task_id: str,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_attach_run_owner_task_id,
            run_id,
            user_id,
            owner_task_id,
        )

    async def complete_run_completed(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        result_excerpt: str | None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await complete_automation_run_completed(
            self._deps,
            self._database_notifications,
            self.config,
            run_id=run_id,
            user_id=user_id,
            finished_at_ms=finished_at_ms,
            result_excerpt=result_excerpt,
        )

    async def complete_run_cancelled(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        status_message: str,
        result_excerpt: str | None = None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await complete_automation_run_cancelled(
            self._deps,
            self._database_notifications,
            self.config,
            run_id=run_id,
            user_id=user_id,
            finished_at_ms=finished_at_ms,
            status_message=status_message,
            result_excerpt=result_excerpt,
        )

    async def complete_run_error(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        status_message: str,
        result_excerpt: str | None = None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await complete_automation_run_error(
            self._deps,
            self._database_notifications,
            self.config,
            run_id=run_id,
            user_id=user_id,
            finished_at_ms=finished_at_ms,
            status_message=status_message,
            result_excerpt=result_excerpt,
        )

    async def complete_run_abandoned(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        status_message: str,
        result_excerpt: str | None = None,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await complete_automation_run_abandoned(
            self._deps,
            self._database_notifications,
            self.config,
            run_id=run_id,
            user_id=user_id,
            finished_at_ms=finished_at_ms,
            status_message=status_message,
            result_excerpt=result_excerpt,
        )

    async def list_runs_for_window(
        self,
        user_id: int,
        *,
        from_utc_ms: int,
        to_utc_ms: int,
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_automation_run_window_records(
            self.core,
            user_id=user_id,
            from_utc_ms=from_utc_ms,
            to_utc_ms=to_utc_ms,
        )

    async def get_run_for_execution(self, run_id: str) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await get_automation_run_for_execution(self.core, run_id=run_id)

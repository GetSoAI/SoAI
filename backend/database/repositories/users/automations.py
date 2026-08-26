"""SoAI - User automation repository [backend/database/repositories/users/automations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.automation_claim_operations import sync_claim_due_runs
from database.repositories.users.automation_conversation_settings_propagation import (
    sync_propagate_automation_conversation_model_settings,
)
from database.repositories.users.automation_read_queries import (
    get_automation,
    has_active_runs,
    list_automations,
    list_due_automations,
    list_enabled_automation_window_sources,
    list_enabled_automations,
)
from database.repositories.users.automation_update_operations import (
    sync_update_automation,
    sync_update_automation_and_abandon_disabled_runs,
)
from database.repositories.users.automation_write_operations import (
    sync_create_automation,
    sync_delete_automation,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from core.automation.automation_mutation_results import AutomationConversationVersion
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseAutomations",)


def _sync_claim_due_runs_with_params(
    conn: sqlite3.Connection,
    automation_id: str,
    now_ms: int,
    expected_next_run_at: int,
    max_run_slots: int,
) -> list[JSONDict]:
    return sync_claim_due_runs(
        conn,
        automation_id,
        now_ms=now_ms,
        expected_next_run_at=expected_next_run_at,
        max_run_slots=max_run_slots,
    )


def _sync_update_automation_and_abandon_disabled_runs_with_params(
    conn: sqlite3.Connection,
    automation_id: str,
    user_id: int,
    payload: JSONDict,
    disallowed_unqualified_tools: tuple[str, ...],
    finished_at_ms: int,
    status_message: str,
) -> tuple[JSONDict | None, list[str], list[str]]:
    return sync_update_automation_and_abandon_disabled_runs(
        conn,
        automation_id,
        user_id,
        payload,
        disallowed_unqualified_tools,
        status_message=status_message,
        finished_at_ms=finished_at_ms,
    )


class DatabaseAutomations:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core

    async def create_automation(self, user_id: int, payload: JSONDict) -> JSONDict:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        disallowed_unqualified_tools = load_automation_disallowed_unqualified_tools(
            self._deps.config,
        )
        result = await self.core.writer.queue_write_operation(
            sync_create_automation,
            user_id,
            payload,
            disallowed_unqualified_tools,
        )
        notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def get_automation(self, automation_id: str, user_id: int) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await get_automation(self.core, automation_id=automation_id, user_id=user_id)

    async def list_automations(
        self,
        user_id: int,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[JSONDict], bool]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_automations(self.core, user_id=user_id, limit=limit, offset=offset)

    async def update_automation(
        self,
        automation_id: str,
        user_id: int,
        payload: JSONDict,
    ) -> JSONDict | None:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        disallowed_unqualified_tools = load_automation_disallowed_unqualified_tools(
            self._deps.config,
        )
        result = await self.core.writer.queue_write_operation(
            sync_update_automation,
            automation_id,
            user_id,
            payload,
            disallowed_unqualified_tools,
        )
        if isinstance(result, dict):
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def propagate_automation_conversation_model_settings(
        self,
        automation_id: str,
        user_id: int,
        model_settings: JSONDict,
    ) -> tuple[AutomationConversationVersion, ...]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await self.core.writer.queue_write_operation(
            sync_propagate_automation_conversation_model_settings,
            automation_id,
            user_id,
            model_settings,
        )

    async def update_automation_and_abandon_disabled_runs(
        self,
        automation_id: str,
        user_id: int,
        payload: JSONDict,
        *,
        finished_at_ms: int,
        status_message: str,
    ) -> tuple[JSONDict | None, list[str], list[str]]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        disallowed_unqualified_tools = load_automation_disallowed_unqualified_tools(
            self._deps.config,
        )
        result = await self.core.writer.queue_write_operation(
            _sync_update_automation_and_abandon_disabled_runs_with_params,
            automation_id,
            user_id,
            payload,
            disallowed_unqualified_tools,
            finished_at_ms,
            status_message,
        )
        if isinstance(result[0], dict) or result[1] or result[2]:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def delete_automation(self, automation_id: str, user_id: int) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        deleted = await self.core.writer.queue_write_operation(
            sync_delete_automation,
            automation_id,
            user_id,
        )
        if deleted:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return deleted

    async def list_enabled_automations(self, user_id: int) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_enabled_automations(self.core, user_id=user_id)

    async def list_enabled_automation_window_sources(self, user_id: int) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_enabled_automation_window_sources(self.core, user_id=user_id)

    async def list_due_automations(self, now_ms: int, limit: int) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await list_due_automations(self.core, now_ms=now_ms, limit=limit)

    async def claim_due_runs(
        self,
        automation_id: str,
        *,
        now_ms: int,
        expected_next_run_at: int,
        max_run_slots: int,
    ) -> list[JSONDict]:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            _sync_claim_due_runs_with_params,
            automation_id,
            now_ms,
            expected_next_run_at,
            max_run_slots,
        )
        if result:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

    async def has_active_runs(self, automation_id: str, user_id: int) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        return await has_active_runs(self.core, automation_id=automation_id, user_id=user_id)

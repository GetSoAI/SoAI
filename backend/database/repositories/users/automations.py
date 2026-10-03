"""SoAI - User automation repository [backend/database/repositories/users/automations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.automation.automation_interactive_tool_approval import strip_interactive_tool_approval
from core.automation.automation_mutation_results import (
    AutomationPreparedUpdate,
    AutomationUpdateResult,
)
from core.automation.automation_revision import (
    compute_automation_revision,
    require_automation_revision_match,
)
from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.automation.automation_update_validation import resolve_automation_update
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from database.core.flags import FEATURE_PROMPTS
from database.repositories.users.automation_claim_operations import sync_claim_due_runs
from database.repositories.users.automation_definition_commit import sync_commit_automation_update
from database.repositories.users.automation_read_queries import (
    get_automation,
    has_active_runs,
    list_automations,
    list_due_automations,
    list_enabled_automation_window_sources,
    list_enabled_automations,
)
from database.repositories.users.automation_write_operations import (
    sync_create_automation,
    sync_delete_automation,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
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


class DatabaseAutomations:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core

    async def prepare_automation_update(
        self,
        automation_id: str,
        user_id: int,
        payload: JSONDict,
        *,
        expected_revision: str | None,
    ) -> AutomationPreparedUpdate | None:
        current = await self.get_automation(automation_id, user_id)
        if current is None:
            return None
        require_automation_revision_match(current, expected_revision)
        validated, _changed = resolve_automation_update(
            current,
            payload,
            now_ms=epoch_ms(),
            disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
                self._deps.config
            ),
        )
        settings = validated["model_settings"]
        if not isinstance(settings, dict):
            raise StateError("Validated automation model settings are invalid.")
        return AutomationPreparedUpdate(
            automation_id=automation_id,
            user_id=user_id,
            payload=dict(payload),
            expected_revision=compute_automation_revision(current),
            model_settings=(
                settings
                if strip_interactive_tool_approval(settings) != current["model_settings"]
                or validated["interactive_tool_approval"] != current["interactive_tool_approval"]
                else None
            ),
        )

    async def commit_automation_update(
        self,
        prepared: AutomationPreparedUpdate,
        conversation_model_settings: JSONDict | None,
    ) -> AutomationUpdateResult:
        self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
        result = await self.core.writer.queue_write_operation(
            sync_commit_automation_update,
            prepared,
            conversation_model_settings,
            load_automation_disallowed_unqualified_tools(self._deps.config),
        )
        if result.automation is not None:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return result

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

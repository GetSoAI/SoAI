"""SoAI - WebUI database automation protocol definitions [backend/core/automation/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.automation.automation_mutation_results import AutomationConversationVersion
    from core.types.json import JSONDict

__all__ = (
    "DatabaseAutomationOccurrenceDeletionsProtocol",
    "DatabaseAutomationRunSchedulerProtocol",
    "DatabaseAutomationRunsProtocol",
    "DatabaseAutomationsProtocol",
)


class DatabaseAutomationsProtocol(Protocol):
    async def create_automation(self, user_id: int, payload: JSONDict) -> JSONDict: ...
    async def get_automation(self, automation_id: str, user_id: int) -> JSONDict | None: ...
    async def list_automations(
        self,
        user_id: int,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[JSONDict], bool]: ...
    async def update_automation(
        self,
        automation_id: str,
        user_id: int,
        payload: JSONDict,
    ) -> JSONDict | None: ...
    async def propagate_automation_conversation_model_settings(
        self,
        automation_id: str,
        user_id: int,
        model_settings: JSONDict,
    ) -> tuple[AutomationConversationVersion, ...]: ...
    async def update_automation_and_abandon_disabled_runs(
        self,
        automation_id: str,
        user_id: int,
        payload: JSONDict,
        *,
        finished_at_ms: int,
        status_message: str,
    ) -> tuple[JSONDict | None, list[str], list[str]]: ...
    async def delete_automation(self, automation_id: str, user_id: int) -> bool: ...
    async def list_enabled_automations(self, user_id: int) -> list[JSONDict]: ...
    async def list_enabled_automation_window_sources(self, user_id: int) -> list[JSONDict]: ...
    async def list_due_automations(self, now_ms: int, limit: int) -> list[JSONDict]: ...
    async def claim_due_runs(
        self,
        automation_id: str,
        *,
        now_ms: int,
        expected_next_run_at: int,
        max_run_slots: int,
    ) -> list[JSONDict]: ...
    async def has_active_runs(self, automation_id: str, user_id: int) -> bool: ...


class DatabaseAutomationRunsProtocol(Protocol):
    async def get_run(self, run_id: str, user_id: int) -> JSONDict | None: ...
    async def list_active_runs(self, user_id: int) -> list[JSONDict]: ...
    async def list_active_run_ids_for_conversation(
        self,
        user_id: int,
        *,
        conv_id: str,
    ) -> list[str]: ...
    async def list_runs(
        self,
        user_id: int,
        *,
        from_utc_ms: int,
        to_utc_ms: int,
        automation_id: str | None,
        limit: int,
        offset: int,
    ) -> list[JSONDict]: ...
    async def create_run_now(self, automation_id: str, user_id: int, now_ms: int) -> JSONDict: ...
    async def mark_run_running(self, run_id: str, *, now_ms: int) -> JSONDict | None: ...
    async def attach_conversation(
        self,
        run_id: str,
        user_id: int,
        conv_id: str,
        *,
        now_ms: int,
    ) -> JSONDict | None: ...
    async def list_runs_for_window(
        self,
        user_id: int,
        *,
        from_utc_ms: int,
        to_utc_ms: int,
    ) -> list[JSONDict]: ...
    async def attach_owner_task_id(
        self,
        run_id: str,
        user_id: int,
        owner_task_id: str,
    ) -> JSONDict | None: ...
    async def complete_run_completed(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        result_excerpt: str | None,
    ) -> JSONDict | None: ...
    async def complete_run_cancelled(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        status_message: str,
        result_excerpt: str | None = None,
    ) -> JSONDict | None: ...
    async def complete_run_error(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        status_message: str,
        result_excerpt: str | None = None,
    ) -> JSONDict | None: ...
    async def complete_run_abandoned(
        self,
        run_id: str,
        user_id: int,
        *,
        finished_at_ms: int,
        status_message: str,
        result_excerpt: str | None = None,
    ) -> JSONDict | None: ...
    async def get_run_for_execution(self, run_id: str) -> JSONDict | None: ...


class DatabaseAutomationOccurrenceDeletionsProtocol(Protocol):
    async def list_occurrence_deletions_for_window(
        self,
        user_id: int,
        *,
        from_utc_ms: int,
        to_utc_ms: int,
    ) -> set[tuple[str, int]]: ...
    async def delete_occurrences(
        self,
        user_id: int,
        *,
        occurrences: list[tuple[str, int]],
        deleted_at_ms: int,
    ) -> JSONDict: ...


class DatabaseAutomationRunSchedulerProtocol(Protocol):
    async def count_active_runs_by_user(self) -> dict[int, int]: ...
    async def mark_restarted_running_runs(
        self,
        *,
        now_ms: int,
        status_message: str,
    ) -> list[JSONDict]: ...
    async def list_queued_run_ids(self) -> list[str]: ...
    async def list_running_run_summaries(self, *, limit: int) -> list[JSONDict]: ...

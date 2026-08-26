"""SoAI - WebUI database agent protocol definitions [backend/core/conversations/protocols_database_agents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.database.requests import (
        ClaimAgentTurnStateRequest,
        WriteAgentTurnStateRequest,
    )
    from core.types.json import JSONDict

__all__ = (
    "DatabaseAgentEventSequencesProtocol",
    "DatabaseAgentPlanProtocol",
    "DatabaseAgentTodoStateProtocol",
    "DatabaseAgentTurnProcessBoundaryProtocol",
    "DatabaseAgentTurnsProtocol",
)


class DatabaseAgentTurnProcessBoundaryProtocol(Protocol):
    async def query_running_turns_from_other_boots(
        self,
        *,
        current_boot_id: str,
        limit: int,
    ) -> list[JSONDict]: ...

    async def query_all_running_turns(self, *, limit: int) -> list[JSONDict]: ...

    async def query_terminal_subagent_turns_with_active_parent_tool_calls(
        self,
        *,
        limit: int,
    ) -> list[JSONDict]: ...

    async def query_terminal_root_turn_active_tool_calls(self, *, limit: int) -> list[JSONDict]: ...


class DatabaseAgentTurnsProtocol(Protocol):
    async def write_turn_state(self, request: WriteAgentTurnStateRequest) -> JSONDict: ...

    async def claim_turn_state(self, request: ClaimAgentTurnStateRequest) -> JSONDict: ...

    async def write_turn_token_usage(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        execution_token: str,
        token_usage: JSONDict,
        updated_at_ms: int | None = None,
    ) -> JSONDict | None: ...

    async def write_turn_assistant_text(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        execution_token: str,
        assistant_text: str,
        updated_at_ms: int | None = None,
    ) -> JSONDict | None: ...

    async def abandon_running_turn_if_current(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
        execution_token: str,
        finished_at_ms: int,
    ) -> JSONDict | None: ...

    async def get_latest_finalized_turn(self, *, conv_id: str, user_id: int) -> JSONDict | None: ...

    async def get_running_root_turn(self, *, conv_id: str, user_id: int) -> JSONDict | None: ...

    async def get_turn(self, *, conv_id: str, user_id: int, turn_id: str) -> JSONDict | None: ...

    async def get_subagent_turn(
        self,
        *,
        conv_id: str,
        user_id: int,
        turn_id: str,
    ) -> JSONDict | None: ...

    async def get_running_root_turns(self, *, conv_id: str, user_id: int) -> list[JSONDict]: ...

    async def get_running_subagent_turns(
        self,
        *,
        conv_id: str,
        user_id: int,
        parent_turn_id: str,
    ) -> list[JSONDict]: ...

    async def list_subagent_summaries(
        self,
        *,
        conv_id: str,
        user_id: int,
        parent_turn_id: str | None = None,
    ) -> list[JSONDict]: ...


class DatabaseAgentEventSequencesProtocol(Protocol):
    async def reserve_sequence_range(
        self,
        *,
        conv_id: str,
        user_id: int,
        count: int,
    ) -> JSONDict: ...
    async def get_current_sequence(self, *, conv_id: str, user_id: int) -> int: ...


class DatabaseAgentTodoStateProtocol(Protocol):
    async def get_todo_state(self, *, conv_id: str, user_id: int) -> JSONDict | None: ...

    async def upsert_todo_state(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        explanation: str | None,
        todo: list[JSONDict],
    ) -> bool: ...

    async def upsert_todo_state_if_no_running_turn(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        explanation: str | None,
        todo: list[JSONDict],
    ) -> bool: ...


class DatabaseAgentPlanProtocol(Protocol):
    async def read_plan(self, *, conv_id: str, user_id: int) -> JSONDict | None: ...

    async def upsert_plan(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        title: str | None,
        markdown: str | None,
    ) -> bool: ...

    async def upsert_plan_if_no_running_turn(
        self,
        *,
        conv_id: str,
        user_id: int,
        revision: int,
        updated_at_ms: int,
        title: str | None,
        markdown: str | None,
    ) -> bool: ...

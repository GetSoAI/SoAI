"""SoAI - Terminal service implementation [backend/terminal/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.terminal.pty_validation import (
    normalize_required_session_id,
    require_positive_pty_dimensions,
)
from core.terminal.requests import CreatePTYSessionRequest
from terminal.dependencies import TerminalServiceDependencies
from terminal.process_operations import (
    execute_system_action_async,
    get_process_list_async,
    kill_process_async,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("Terminal",)


class Terminal:

    def __init__(self, deps: TerminalServiceDependencies) -> None:
        self._logger = deps.logger
        self._command_executor = deps.command_executor
        self._runtime_flags = deps.runtime_flags
        self._enabled = deps.terminal_enabled
        self._session_manager = deps.pty_session_manager

    async def create_pty_session(
        self,
        request: CreatePTYSessionRequest,
    ) -> JSONDict:
        if not self._enabled:
            raise StateError("Terminal access is disabled.")
        return await self._session_manager.create_session(request)

    async def write_pty_input(self, session_id: str, data: bytes) -> None:
        normalized_session_id = normalize_required_session_id(session_id)
        if not data:
            return
        await self._session_manager.write_input(normalized_session_id, data)

    async def resize_pty(self, session_id: str, cols: int, rows: int) -> None:
        normalized_session_id = normalize_required_session_id(session_id)
        require_positive_pty_dimensions(cols, rows)
        await self._session_manager.resize(normalized_session_id, cols, rows)

    async def close_pty_session(self, session_id: str) -> None:
        normalized_session_id = normalize_required_session_id(session_id)
        await self._session_manager.close_session(normalized_session_id)

    async def close_pty_sessions_for_user(self, user_id: int) -> int:
        return await self._session_manager.close_sessions_for_user(user_id)

    async def get_process_list(self, filter_str: str | None = None) -> list[JSONDict]:
        normalized_filter: str | None = None
        if filter_str is not None:
            stripped_filter = filter_str.strip()
            normalized_filter = stripped_filter or None
        return await get_process_list_async(normalized_filter)

    async def kill_process(
        self,
        pid: int,
        signal_to_send: int = 15,
        use_sudo: bool = False,
    ) -> tuple[bool, str]:
        return await kill_process_async(self._command_executor, pid, signal_to_send, use_sudo)

    async def system_action(
        self,
        action: str,
        args: list[str] | None = None,
        use_sudo: bool = False,
    ) -> tuple[bool, str]:
        return await execute_system_action_async(
            self._command_executor,
            self._runtime_flags,
            action,
            args,
            use_sudo,
        )

    async def shutdown(self) -> None:
        self._logger.debug("Terminal shutting down.")
        await self._session_manager.shutdown()

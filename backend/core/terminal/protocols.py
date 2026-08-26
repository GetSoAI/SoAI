"""SoAI - Core contracts for terminal cross-subsystem interfaces [backend/core/terminal/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.terminal.requests import CreatePTYSessionRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("TerminalServiceProtocol",)


@runtime_checkable
class TerminalServiceProtocol(Protocol):
    async def create_pty_session(self, request: CreatePTYSessionRequest) -> JSONDict: ...

    async def write_pty_input(self, session_id: str, data: bytes) -> None: ...

    async def resize_pty(self, session_id: str, cols: int, rows: int) -> None: ...

    async def close_pty_session(self, session_id: str) -> None: ...

    async def close_pty_sessions_for_user(self, user_id: int) -> int: ...

    async def get_process_list(self, filter_str: str | None = None) -> list[JSONDict]: ...

    async def kill_process(
        self,
        pid: int,
        signal_to_send: int = 15,
        use_sudo: bool = False,
    ) -> tuple[bool, str]: ...

    async def system_action(
        self,
        action: str,
        args: list[str] | None = None,
        use_sudo: bool = False,
    ) -> tuple[bool, str]: ...

    async def shutdown(self) -> None: ...

"""SoAI - Terminal internal protocols [backend/terminal/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.terminal.requests import CreatePTYSessionRequest
    from core.types.json_value import JSONDict

__all__ = (
    "PTYSessionManagerProtocol",
    "WindowsPTYProtocol",
)


class WindowsPTYProtocol(Protocol):
    pid: int | None

    def spawn(
        self,
        appname: str,
        cmdline: str | None = None,
        cwd: str | None = None,
        env: str | None = None,
    ) -> bool: ...

    def set_size(self, cols: int, rows: int) -> None: ...

    def write(self, data: str) -> None: ...

    def read(self, blocking: bool = False) -> str: ...

    def isalive(self) -> bool: ...

    def iseof(self) -> bool: ...

    def get_exitstatus(self) -> int | None: ...

    def cancel_io(self) -> bool: ...


class PTYSessionManagerProtocol(Protocol):
    async def create_session(
        self,
        request: CreatePTYSessionRequest,
    ) -> JSONDict: ...

    async def write_input(self, session_id: str, data: bytes) -> None: ...

    async def resize(self, session_id: str, cols: int, rows: int) -> None: ...

    async def close_session(self, session_id: str) -> None: ...

    async def close_sessions_for_user(self, user_id: int) -> int: ...

    async def shutdown(self) -> None: ...

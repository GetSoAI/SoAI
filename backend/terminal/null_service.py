"""SoAI - Null terminal service for unavailable hardware environments [backend/terminal/null_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.logging.protocols import TraceLogger
from core.terminal.requests import CreatePTYSessionRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "NullTerminalService",
    "NullTerminalServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class NullTerminalServiceDependencies:
    logger: TraceLogger

    def __post_init__(self) -> None:
        require_dependencies(
            owner="NullTerminalServiceDependencies",
            logger=self.logger,
        )


class NullTerminalService:
    def __init__(self, deps: NullTerminalServiceDependencies) -> None:
        self._logger = deps.logger

    def _raise_unavailable(self) -> NoReturn:
        raise ValidationError("Terminal service is not available.")

    async def create_pty_session(
        self,
        request: CreatePTYSessionRequest,
    ) -> JSONDict:
        _ = request
        self._raise_unavailable()

    async def write_pty_input(self, session_id: str, data: bytes) -> None:
        _ = (session_id, data)
        self._raise_unavailable()

    async def resize_pty(self, session_id: str, cols: int, rows: int) -> None:
        _ = (session_id, cols, rows)
        self._raise_unavailable()

    async def close_pty_session(self, session_id: str) -> None:
        _ = session_id
        self._raise_unavailable()

    async def close_pty_sessions_for_user(self, user_id: int) -> int:
        _ = user_id
        self._raise_unavailable()

    async def get_process_list(self, filter_str: str | None = None) -> list[JSONDict]:
        _ = filter_str
        return []

    async def kill_process(
        self,
        pid: int,
        signal_to_send: int = 15,
        use_sudo: bool = False,
    ) -> tuple[bool, str]:
        _ = (pid, signal_to_send, use_sudo)
        self._raise_unavailable()

    async def system_action(
        self,
        action: str,
        args: list[str] | None = None,
        use_sudo: bool = False,
    ) -> tuple[bool, str]:
        _ = (action, args, use_sudo)
        self._raise_unavailable()

    async def shutdown(self) -> None:
        self._logger.debug("NullTerminalService shutdown called.")

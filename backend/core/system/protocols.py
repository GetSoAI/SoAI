"""SoAI - System-level protocols [backend/core/system/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.system.power_operations import PowerOperation, PowerOperationAction
    from core.types.json import JSONValue

    type Command = str | Sequence[str]

__all__ = (
    "AsyncCommandExecutorProtocol",
    "CommandExecutorProtocol",
    "CommandResultProtocol",
    "ManagedProcessProtocol",
    "PowerOperationRepositoryProtocol",
    "PowerOperationSupervisorProtocol",
    "StartupInfoProtocol",
)


class PowerOperationRepositoryProtocol(Protocol):
    async def accept(
        self,
        *,
        operation_id: str,
        owner_id: int,
        action: PowerOperationAction,
        force: bool,
        delay_ms: int,
        accepted_at_ms: int,
    ) -> PowerOperation: ...

    async def get(self, operation_id: str) -> PowerOperation | None: ...
    async def get_active(self) -> PowerOperation | None: ...
    async def cancel(self, operation_id: str, *, cancelled_at_ms: int) -> PowerOperation: ...

    async def claim_due(
        self,
        *,
        now_ms: int,
        claim_owner: str,
        lease_duration_ms: int,
        max_attempts: int,
    ) -> PowerOperation | None: ...

    async def mark_dispatch_started(
        self,
        operation_id: str,
        *,
        claim_owner: str,
        dispatch_started_at_ms: int,
    ) -> PowerOperation: ...

    async def complete(
        self,
        operation_id: str,
        *,
        claim_owner: str,
        completed_at_ms: int,
        result_code: str,
    ) -> PowerOperation: ...

    async def fail(
        self,
        operation_id: str,
        *,
        claim_owner: str,
        completed_at_ms: int,
        error_code: str,
    ) -> PowerOperation: ...

    async def reconcile(self, *, now_ms: int, max_attempts: int) -> tuple[PowerOperation, ...]: ...
    async def next_wake_at_ms(self) -> int | None: ...


class PowerOperationSupervisorProtocol(Protocol):
    @property
    def is_ready(self) -> bool: ...

    async def start(self) -> None: ...
    async def shutdown(self) -> None: ...

    async def accept(
        self,
        *,
        operation_id: str,
        owner_id: int,
        action: PowerOperationAction,
        force: bool,
        delay_ms: int,
    ) -> PowerOperation: ...

    async def get(self, operation_id: str) -> PowerOperation | None: ...
    async def get_active(self) -> PowerOperation | None: ...
    async def cancel(self, operation_id: str) -> PowerOperation: ...


class StartupInfoProtocol(Protocol): ...


class ManagedProcessProtocol(Protocol):
    pid: int

    def poll(self) -> int | None: ...


class CommandResultProtocol(Protocol):
    @property
    def stdout(self) -> str: ...

    @property
    def return_code(self) -> int: ...

    @property
    def stderr(self) -> str: ...


class CommandExecutorProtocol(Protocol):
    def execute(
        self,
        command: Command,
        *,
        timeout: int,
        shell: bool,
        use_sudo: bool,
        stdin_text: str | None = None,
    ) -> CommandResultProtocol: ...


class AsyncCommandExecutorProtocol(Protocol):
    async def execute(
        self,
        argv: Sequence[str],
        *,
        timeout_sec: float,
        cancellation_id: str,
        owner: str,
        metadata: dict[str, JSONValue] | None = None,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
        on_stderr_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> CommandResultProtocol: ...

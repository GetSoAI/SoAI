"""SoAI - Host command failure normalization helpers [backend/core/system/command_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, NoReturn

from core.errors.exceptions import PreconditionError, ProcessError

if TYPE_CHECKING:
    from core.system.protocols import (
        AsyncCommandExecutorProtocol,
        CommandResultProtocol,
    )
    from core.types.json import JSONValue

__all__ = (
    "build_command_failure_details",
    "execute_async_command_and_require_success",
    "has_systemd_bus_error",
    "raise_precondition_error_for_result",
    "raise_process_error_for_result",
    "require_command_success",
)


def build_command_failure_details(
    *,
    argv: Sequence[str],
    result: CommandResultProtocol,
    include_stdout: bool = True,
    include_argv: bool = True,
) -> dict[str, str | int | list[str]]:
    details: dict[str, str | int | list[str]] = {
        "stderr": (result.stderr or "").strip(),
        "return_code": result.return_code,
    }
    if include_stdout:
        details["stdout"] = (result.stdout or "").strip()
    if include_argv:
        details["argv"] = [str(part) for part in argv]
    return details


def has_systemd_bus_error(*, stdout: str, stderr: str) -> bool:
    message = stderr or stdout
    return (
        "System has not been booted with systemd" in message
        or "Failed to connect to bus" in message
    )


def require_command_success(
    result: CommandResultProtocol,
    argv: Sequence[str],
    *,
    operation: str,
) -> None:
    if result.return_code == 0:
        return
    raise_process_error_for_result(argv=argv, result=result, operation=operation)


def raise_precondition_error_for_result(
    *,
    argv: Sequence[str],
    result: CommandResultProtocol,
    message: str,
    operation: str,
) -> NoReturn:
    raise PreconditionError(
        message,
        operation=operation,
        details=build_command_failure_details(argv=argv, result=result),
    )


def raise_process_error_for_result(
    *,
    argv: Sequence[str],
    result: CommandResultProtocol,
    operation: str,
    message: str | None = None,
    include_stdout: bool = True,
    include_argv: bool = True,
) -> NoReturn:
    resolved_message = (
        message
        if message is not None
        else f"Command failed ({result.return_code}): {' '.join([str(part) for part in argv])}"
    )
    raise ProcessError(
        resolved_message,
        operation=operation,
        details=build_command_failure_details(
            argv=argv,
            result=result,
            include_stdout=include_stdout,
            include_argv=include_argv,
        ),
    )


async def execute_async_command_and_require_success(
    executor: AsyncCommandExecutorProtocol,
    argv: Sequence[str],
    *,
    timeout_sec: float,
    cancellation_id: str,
    owner: str,
    operation: str,
    metadata: dict[str, JSONValue] | None = None,
    on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    on_stderr_line: Callable[[str], Awaitable[None]] | None = None,
) -> CommandResultProtocol:
    result = await executor.execute(
        list(argv),
        timeout_sec=timeout_sec,
        cancellation_id=cancellation_id,
        owner=owner,
        metadata=metadata,
        on_stdout_line=on_stdout_line,
        on_stderr_line=on_stderr_line,
    )
    require_command_success(result, argv, operation=operation)
    return result

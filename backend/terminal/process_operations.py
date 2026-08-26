"""SoAI - Stateless process management operations [backend/terminal/process_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.system.commands import execute_system_action, kill_process_native
from core.system.processes import get_process_list, kill_process_psutil

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "execute_system_action_async",
    "get_process_list_async",
    "kill_process_async",
)


async def get_process_list_async(filter_str: str | None = None) -> list[JSONDict]:
    return await asyncio.to_thread(get_process_list, filter_str)


async def kill_process_async(
    command_executor: CommandExecutorProtocol,
    pid: int,
    signal_to_send: int = 15,
    use_sudo: bool = False,
) -> tuple[bool, str]:
    if use_sudo:
        return await asyncio.to_thread(
            kill_process_native,
            command_executor,
            pid,
            signal_to_send,
            True,
        )
    return await asyncio.to_thread(kill_process_psutil, pid, signal_to_send)


async def execute_system_action_async(
    command_executor: CommandExecutorProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    action: str,
    args: list[str] | None = None,
    use_sudo: bool = False,
) -> tuple[bool, str]:
    if runtime_flags.host_system_actions_disabled:
        return (False, "System actions are disabled by runtime policy.")
    return await asyncio.to_thread(execute_system_action, command_executor, action, args, use_sudo)

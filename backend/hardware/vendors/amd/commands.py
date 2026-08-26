"""SoAI - AMD SMI command runner [backend/hardware/vendors/amd/commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from hardware.vendors.command_probe import require_json_command_payload

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONValue

__all__ = (
    "execute_amd_smi_command",
    "execute_amd_smi_json_command",
    "execute_amd_smi_reset_command",
)

_AMD_SMI_ACCEPT_TERMS_STDIN = "y\n"


def execute_amd_smi_json_command(
    executor: CommandExecutorProtocol,
    command: list[str],
    *,
    timeout: int = 10,
    use_sudo: bool = False,
) -> JSONValue:
    return require_json_command_payload(
        executor,
        command,
        timeout=timeout,
        use_sudo=use_sudo,
        failure_message="amd-smi command failed",
    )


def execute_amd_smi_command(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    command: list[str],
) -> None:
    cmd = ["amd-smi", "set", "-g", str(vendor_id)] + command
    result = executor.execute(
        cmd,
        timeout=10,
        shell=False,
        use_sudo=True,
        stdin_text=_AMD_SMI_ACCEPT_TERMS_STDIN,
    )
    if result.return_code != 0:
        raise StateError(result.stderr or "amd-smi command failed")


def execute_amd_smi_reset_command(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    command: list[str],
) -> None:
    cmd = ["amd-smi", "reset", "-g", str(vendor_id)] + command
    result = executor.execute(cmd, timeout=5, shell=False, use_sudo=True)
    if result.return_code != 0:
        raise StateError(result.stderr or "amd-smi reset command failed")

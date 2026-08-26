"""SoAI - Intel XPU-SMI command helpers [backend/hardware/vendors/intel/commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from hardware.vendors.command_probe import require_json_command_payload
from hardware.vendors.intel.runtime import resolve_xpu_smi_path

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONValue

__all__ = (
    "execute_intel_config_command",
    "execute_intel_config_json",
    "execute_intel_dump_json",
    "execute_intel_json_command",
)


def execute_intel_json_command(
    executor: CommandExecutorProtocol,
    command: list[str],
    *,
    timeout: int,
    use_sudo: bool,
) -> JSONValue:
    return require_json_command_payload(
        executor,
        command,
        timeout=timeout,
        use_sudo=use_sudo,
        failure_message="xpu-smi command failed",
    )


def execute_intel_config_json(
    executor: CommandExecutorProtocol,
    vendor_id: int,
) -> JSONValue:
    return execute_intel_json_command(
        executor,
        [resolve_xpu_smi_path(), "config", "-d", str(vendor_id), "-j"],
        timeout=5,
        use_sudo=False,
    )


def execute_intel_dump_json(
    executor: CommandExecutorProtocol,
    vendor_id: int | None = None,
) -> JSONValue:
    command = [resolve_xpu_smi_path(), "dump"]
    if vendor_id is not None:
        command.extend(["-d", str(vendor_id)])
    command.append("-j")
    return execute_intel_json_command(
        executor,
        command,
        timeout=10,
        use_sudo=False,
    )


def execute_intel_config_command(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    args: tuple[str, ...],
    *,
    use_sudo: bool,
) -> None:
    command = [resolve_xpu_smi_path(), "config", "-d", str(vendor_id), *args]
    result = executor.execute(command, timeout=5, shell=False, use_sudo=use_sudo)
    if result.return_code != 0:
        raise StateError(result.stderr or "xpu-smi config command failed")

"""SoAI - AMD SMI command runner [backend/hardware/vendors/amd/commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.validation.strict_integer import is_strict_int
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
        framing="amd_smi",
    )


def execute_amd_smi_command(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    command: list[str],
) -> None:
    if "--clk-level" in command:
        raise StateError("AMD SMI clock command syntax is unproved for the selected backend.")
    cmd = ["amd-smi", "set", "-g", str(vendor_id)] + command
    result = executor.execute(
        cmd,
        timeout=10,
        shell=False,
        use_sudo=True,
        stdin_text=_AMD_SMI_ACCEPT_TERMS_STDIN,
    )
    _require_amd_control_command_success(result.return_code, result.stdout, result.stderr)


def execute_amd_smi_reset_command(
    executor: CommandExecutorProtocol,
    vendor_id: int,
    command: list[str],
) -> None:
    cmd = ["amd-smi", "reset", "-g", str(vendor_id)] + command
    result = executor.execute(cmd, timeout=5, shell=False, use_sudo=True)
    _require_amd_control_command_success(result.return_code, result.stdout, result.stderr)


def _require_amd_control_command_success(return_code: int, stdout: str, stderr: str) -> None:
    if not is_strict_int(return_code) or not isinstance(stdout, str) or not isinstance(stderr, str):
        raise ValidationError("AMD SMI control command returned a malformed response.")
    diagnostic = re.search(
        r"(?im)(?:^\s*error\b|parameter[^\n]*is invalid|unrecognized arguments:|error code:\s*-[1-9]\d*)",
        f"{stdout}\n{stderr}",
    )
    if return_code != 0 or diagnostic is not None:
        raise StateError(
            "AMD SMI control command failed after invocation.",
            details={
                "return_code": return_code,
                "stdout": stdout,
                "stderr": stderr,
                "actuator_invoked": True,
            },
        )

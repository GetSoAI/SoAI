"""SoAI - AMDGPU OverDrive sysfs settings application [backend/hardware/vendors/amd/overdrive_apply.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.types.json_value import JSONValue
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_tuning.service_parsing import is_auto_gpu_setting
from hardware.vendors.amd.overdrive_state import resolve_amdgpu_overdrive_paths

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol

__all__ = ("apply_amdgpu_overdrive_settings",)

_WRITE_SYSFS_SCRIPT = 'printf "%s\\n" "$1" > "$2"'


def apply_amdgpu_overdrive_settings(
    executor: CommandExecutorProtocol,
    *,
    pci_bdf: str | None,
    reset_clocks: bool,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
) -> list[str]:
    paths = resolve_amdgpu_overdrive_paths(pci_bdf)
    if paths is None:
        raise StateError("AMDGPU OverDrive sysfs controls are unavailable for this GPU.")
    applied_parts: list[str] = []
    commands = _manual_overdrive_commands(
        core_clock=core_clock,
        mem_clock=mem_clock,
    )
    if reset_clocks or _has_auto_value(core_clock, mem_clock):
        _write_sysfs(executor, paths.performance_level_path, "manual")
        _write_sysfs(executor, paths.overdrive_path, "r")
        _write_sysfs(executor, paths.overdrive_path, "c")
        applied_parts.append("OverDrive reset")
    if commands:
        _write_sysfs(executor, paths.performance_level_path, "manual")
        for command in commands:
            _write_sysfs(executor, paths.overdrive_path, command)
        _write_sysfs(executor, paths.overdrive_path, "c")
        applied_parts.extend(_messages_for_commands(commands))
    elif applied_parts:
        _write_sysfs(executor, paths.performance_level_path, "auto")
    return applied_parts


def _has_auto_value(*values: JSONValue | None) -> bool:
    return any(value is not None and is_auto_gpu_setting(value) for value in values)


def _manual_overdrive_commands(
    *,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
) -> list[str]:
    commands: list[str] = []
    core_value = _manual_int_value(core_clock, "Core clock")
    if core_value is not None:
        commands.append(f"s 1 {core_value}")
    mem_value = _manual_int_value(mem_clock, "Memory clock")
    if mem_value is not None:
        commands.append(f"m 1 {mem_value}")
    return commands


def _manual_int_value(value: JSONValue | None, label: str) -> int | None:
    if value is None or is_auto_gpu_setting(value):
        return None
    int_value = coerce_int_from_scalar(value)
    if int_value is None:
        raise ValidationError(f"Invalid {label.lower()} value.")
    return int_value


def _messages_for_commands(commands: list[str]) -> list[str]:
    messages: list[str] = []
    for command in commands:
        parts = command.split()
        if len(parts) == 3 and parts[0] == "s":
            messages.append(f"Core {parts[2]}MHz")
        elif len(parts) == 3 and parts[0] == "m":
            messages.append(f"Memory {parts[2]}MHz")
    return messages


def _write_sysfs(executor: CommandExecutorProtocol, path: str, payload: str) -> None:
    result = executor.execute(
        ["sh", "-c", _WRITE_SYSFS_SCRIPT, "soai-amdgpu-overdrive", payload, path],
        timeout=5,
        shell=False,
        use_sudo=True,
    )
    if result.return_code != 0:
        raise StateError(result.stderr or f"Failed to write AMDGPU OverDrive control {path}.")

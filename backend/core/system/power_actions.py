"""SoAI - System power action helpers [backend/core/system/power_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from core.errors.exceptions import ValidationError
from core.system.power_operations import PowerOperationAction

__all__ = (
    "PowerAction",
    "build_power_terminal_action",
    "resolve_power_action",
)


class PowerAction(str, Enum):
    SHUTDOWN = "shutdown"
    REBOOT = "reboot"
    SUSPEND = "suspend"
    HIBERNATE = "hibernate"


def resolve_power_action(action: PowerOperationAction) -> PowerAction:
    mapping = {
        PowerOperationAction.HOST_SHUTDOWN: PowerAction.SHUTDOWN,
        PowerOperationAction.HOST_REBOOT: PowerAction.REBOOT,
        PowerOperationAction.HOST_SUSPEND: PowerAction.SUSPEND,
        PowerOperationAction.HOST_HIBERNATE: PowerAction.HIBERNATE,
    }
    resolved = mapping.get(action)
    if resolved is None:
        raise ValidationError(
            "Power operation action is not a host action.",
            details={"action": action.value},
        )
    return resolved


def build_power_terminal_action(
    action: PowerAction,
    *,
    force: bool,
    is_windows: bool,
    is_linux: bool,
    is_macos: bool,
) -> tuple[str, list[str]]:
    is_windows = bool(is_windows)
    is_linux = bool(is_linux)
    is_macos = bool(is_macos)

    if sum((is_windows, is_linux, is_macos)) != 1:
        raise ValidationError(
            "Host power actions require a supported runtime platform.",
            details={"action": action.value},
        )

    if is_windows and action is PowerAction.SUSPEND:
        raise ValidationError(
            "System suspend is not supported on Windows.",
            details={"action": action.value, "platform": "Windows"},
        )
    if is_macos and action is PowerAction.HIBERNATE:
        raise ValidationError(
            "System hibernate is not supported on macOS.",
            details={"action": action.value, "platform": "macOS"},
        )
    if is_macos and force:
        raise ValidationError(
            "Forced host power actions are not supported on macOS.",
            details={"action": action.value, "platform": "macOS"},
        )

    if action in {PowerAction.SUSPEND, PowerAction.HIBERNATE}:
        args: list[str] = []
        if is_windows and action is PowerAction.HIBERNATE and force:
            args = ["/f"]
        elif is_linux:
            args = (["--force"] if force else []) + ["--no-block"]
        return (action.value, args)

    if action is PowerAction.SHUTDOWN:
        if is_windows:
            args = ["/s", "/t", "0"] + (["/f"] if force else [])
            return (PowerAction.SHUTDOWN.value, args)
        if is_linux:
            args = (["--force"] if force else []) + ["--no-block"]
            return (PowerAction.SHUTDOWN.value, args)
        if is_macos:
            return (PowerAction.SHUTDOWN.value, [])
        return (PowerAction.SHUTDOWN.value, [])

    if action is PowerAction.REBOOT:
        if is_windows:
            args = ["/r", "/t", "0"] + (["/f"] if force else [])
            return (PowerAction.REBOOT.value, args)
        if is_linux:
            args = (["--force"] if force else []) + ["--no-block"]
            return (PowerAction.REBOOT.value, args)
        if is_macos:
            return (PowerAction.REBOOT.value, [])
        return (PowerAction.REBOOT.value, [])

    raise ValidationError(
        "Unsupported system power action.",
        details={"action": action.value},
    )

"""SoAI - Windows hardware command helpers [backend/hardware/windows_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("build_windows_powershell_command",)


def build_windows_powershell_command(command_text: str) -> list[str]:
    return [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-NoProfile",
        "-Command",
        command_text,
    ]

"""SoAI - Platform-specific subprocess option resolution [backend/core/system/subprocess_platform.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.platform.os import is_windows

if TYPE_CHECKING:
    from core.system.protocols import StartupInfoProtocol

__all__ = (
    "WINDOWS_CREATE_NEW_PROCESS_GROUP",
    "WINDOWS_CREATE_NO_WINDOW",
    "WINDOWS_DETACHED_PROCESS",
    "resolve_subprocess_creationflags",
    "resolve_subprocess_startupinfo",
    "windows_isolated_process_creationflags",
    "windows_no_window_creationflags",
)

WINDOWS_DETACHED_PROCESS: int = 0x00000008
WINDOWS_CREATE_NEW_PROCESS_GROUP: int = 0x00000200
WINDOWS_CREATE_NO_WINDOW: int = 0x08000000


def resolve_subprocess_creationflags(creationflags: int | None) -> int:
    if not is_windows():
        return 0
    return int(creationflags or 0)


def resolve_subprocess_startupinfo(
    startupinfo: StartupInfoProtocol | None,
) -> StartupInfoProtocol | None:
    if not is_windows():
        return None
    return startupinfo


def windows_no_window_creationflags() -> int:
    return resolve_subprocess_creationflags(WINDOWS_CREATE_NO_WINDOW)


def windows_isolated_process_creationflags() -> int:
    return resolve_subprocess_creationflags(
        WINDOWS_CREATE_NEW_PROCESS_GROUP | WINDOWS_CREATE_NO_WINDOW,
    )

"""SoAI - PTY platform session object validation [backend/terminal/platform_session_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from terminal.internal_protocols import WindowsPTYProtocol

__all__ = (
    "require_linux_master_fd",
    "require_windows_master_fd",
)


def require_linux_master_fd(master_fd: int | WindowsPTYProtocol) -> int:
    if not isinstance(master_fd, int):
        raise StateError("Linux PTY session has invalid master fd.")
    return master_fd


def require_windows_master_fd(master_fd: int | WindowsPTYProtocol) -> WindowsPTYProtocol:
    if isinstance(master_fd, int):
        raise StateError("Windows PTY session has invalid master fd.")
    return master_fd

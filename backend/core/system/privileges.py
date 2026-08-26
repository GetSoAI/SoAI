"""SoAI - System administrator privilege detection [backend/core/system/privileges.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.platform.os import is_windows
from core.system.windows_ctypes import resolve_windll

__all__ = ("is_admin",)

LOGGER_NAME = "SoAI.core.system.privileges"
OPERATION = "core.system.privileges.is_admin"


PRIVILEGE_CHECK_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = RECOVERABLE_EXCEPTIONS + (
    RuntimeError,
    TypeError,
    AttributeError,
)


def is_admin() -> bool:
    try:
        if not is_windows():
            return os.geteuid() == 0
        windll = resolve_windll()
        if windll is None:
            raise AttributeError("ctypes.windll unavailable")
        shell32 = windll.shell32
        admin_status: int = shell32.IsUserAnAdmin()
        return admin_status != 0
    except PRIVILEGE_CHECK_RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to determine administrator privileges (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return False

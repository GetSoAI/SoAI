"""SoAI - Windows console service [backend/app/cli/windows_console_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.logging.protocols import LoggerProtocol
from core.system.subprocess_platform import windows_isolated_process_creationflags

__all__ = (
    "WindowsConsoleService",
    "WindowsConsoleServiceDependencies",
)

WINDOWS_CTRL_C_EVENT = 0
WINDOWS_CTRL_BREAK_EVENT = 1
WINDOWS_CTRL_CLOSE_EVENT = 2
WINDOWS_SIGBREAK = 21
WINDOWS_TRUE = 1
WINDOWS_FALSE = 0
HANDLED_CONSOLE_CTRL_EVENTS: frozenset[int] = frozenset(
    {
        WINDOWS_CTRL_C_EVENT,
        WINDOWS_CTRL_BREAK_EVENT,
        WINDOWS_CTRL_CLOSE_EVENT,
    },
)

OPERATION_REGISTER_CTRL_HANDLER = "windows_console_service.register_ctrl_handler"
OPERATION_RELEASE_CTRL_HANDLER = "windows_console_service.release_ctrl_handler"


@dataclass(frozen=True, slots=True)
class WindowsConsoleServiceDependencies:
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="WindowsConsoleServiceDependencies",
            logger=self.logger,
        )


class WindowsConsoleService:
    __slots__ = ("_ctrl_handler_reference", "_logger")

    def __init__(self, deps: WindowsConsoleServiceDependencies) -> None:
        self._logger: LoggerProtocol = deps.logger
        self._ctrl_handler_reference: Callable[[int], int] | None = None

    def get_subprocess_flags(self) -> int:
        if sys.platform != "win32":
            return 0
        return windows_isolated_process_creationflags()

    def ignore_gui_control_signals(self) -> None:
        if sys.platform != "win32":
            return
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(WINDOWS_SIGBREAK, signal.SIG_IGN)

    def register_ctrl_handler(self, handler: Callable[[], None]) -> None:
        if sys.platform != "win32":
            return

        def console_ctrl_handler(ctrl_type: int) -> int:
            if ctrl_type in HANDLED_CONSOLE_CTRL_EVENTS:
                handler()
                return WINDOWS_TRUE
            return WINDOWS_FALSE

        try:
            handler_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)
            callback = handler_type(console_ctrl_handler)
            kernel32 = ctypes.windll.kernel32
            set_console_ctrl_handler = kernel32.SetConsoleCtrlHandler
            set_console_ctrl_handler(callback, True)
        except (AttributeError, TypeError, ValueError, OSError) as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION_REGISTER_CTRL_HANDLER)
            log_handled_exception(
                self._logger,
                coerced,
                message="Failed to register Windows console control handler (non-critical).",
                operation=OPERATION_REGISTER_CTRL_HANDLER,
                level="warning",
            )
            return
        self._ctrl_handler_reference = callback

    def release_ctrl_handler(self) -> None:
        if sys.platform != "win32":
            return
        callback = self._ctrl_handler_reference
        if callback is None:
            return
        try:
            kernel32 = ctypes.windll.kernel32
            set_console_ctrl_handler = kernel32.SetConsoleCtrlHandler
            set_console_ctrl_handler(callback, False)
        except (AttributeError, TypeError, ValueError, OSError) as exception:
            coerced = coerce_to_soai_error(exception, operation=OPERATION_RELEASE_CTRL_HANDLER)
            log_handled_exception(
                self._logger,
                coerced,
                message="Failed to release Windows console control handler (non-critical).",
                operation=OPERATION_RELEASE_CTRL_HANDLER,
                level="warning",
            )
            return
        self._ctrl_handler_reference = None

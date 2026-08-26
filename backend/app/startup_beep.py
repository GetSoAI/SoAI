"""SoAI - Linux startup beep notification [backend/app/startup_beep.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import errno
import os
import platform
import sys
from collections.abc import Awaitable, Callable

from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from core.timing.constants import SHORT_POLL_INTERVAL_SEC

__all__ = (
    "STARTUP_BEEP_CONFIG_KEY",
    "emit_startup_beep_if_enabled",
    "is_linux_host",
)

STARTUP_BEEP_CONFIG_KEY = "SYSTEM.RUNTIME.STARTUP_BEEP"
_LINUX_KDMKTONE_IOCTL = 0x4B30
_PC_SPEAKER_CLOCK_TICK_RATE = 1_193_180
_STARTUP_BEEP_FREQUENCY_HZ = 1200
_STARTUP_BEEP_DURATION_MS = 90
_STARTUP_BEEP_COUNT = 2
_OPERATION_APPLICATION_STARTUP_BEEP = "application_startup.beep"
_SPEAKER_UNAVAILABLE_ERRNOS: frozenset[int] = frozenset(
    {
        errno.EIO,
        errno.ENODEV,
        errno.ENXIO,
        errno.ENOTTY,
        errno.ENOENT,
        errno.EACCES,
        errno.EPERM,
        errno.EOPNOTSUPP,
    }
)

if sys.platform.startswith("linux"):
    import fcntl

    def _linux_ioctl(fd: int, request: int, arg: int) -> int:
        return fcntl.ioctl(fd, request, arg)

else:

    def _linux_ioctl(fd: int, request: int, arg: int) -> int:
        _ = fd, request, arg
        raise StateError("Linux console tone ioctl is unavailable on this platform.")


def is_linux_host() -> bool:
    return platform.system() == "Linux"


def _linux_console_path() -> str:
    return os.path.join(os.sep, "dev", "console")


def _linux_kdmktone_argument() -> int:
    frequency_divisor = _PC_SPEAKER_CLOCK_TICK_RATE // _STARTUP_BEEP_FREQUENCY_HZ
    return frequency_divisor | (_STARTUP_BEEP_DURATION_MS << 16)


def _emit_linux_console_tone() -> None:
    file_descriptor = os.open(_linux_console_path(), os.O_WRONLY)
    try:
        _linux_ioctl(file_descriptor, _LINUX_KDMKTONE_IOCTL, _linux_kdmktone_argument())
    finally:
        os.close(file_descriptor)


async def emit_startup_beep_if_enabled(
    config: ConfigProtocol,
    logger: LoggerProtocol,
    *,
    is_linux_host_func: Callable[[], bool] = is_linux_host,
    tone_emitter: Callable[[], None] = _emit_linux_console_tone,
    sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    if not config.get_bool(STARTUP_BEEP_CONFIG_KEY):
        return
    if not is_linux_host_func():
        return
    try:
        for beep_index in range(_STARTUP_BEEP_COUNT):
            if beep_index > 0:
                await sleep_func(SHORT_POLL_INTERVAL_SEC)
            await asyncio.to_thread(tone_emitter)
    except (OSError, StateError, ValueError) as exception:
        speaker_unavailable = (
            isinstance(exception, OSError) and exception.errno in _SPEAKER_UNAVAILABLE_ERRNOS
        )
        if speaker_unavailable:
            log_handled_exception(
                logger,
                exception,
                message="Startup motherboard beep skipped; PC speaker is unavailable on this host.",
                operation=_OPERATION_APPLICATION_STARTUP_BEEP,
                level="debug",
            )
            return
        log_exception(
            logger,
            exception,
            message="Startup motherboard beep could not be emitted.",
            operation=_OPERATION_APPLICATION_STARTUP_BEEP,
            level="warning",
        )

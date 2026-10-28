"""SoAI - Startup tone through the Linux PC speaker or the Windows audio device [backend/app/startup_beep.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import errno
import io
import math
import os
import platform
import sys
import wave
from array import array
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal

from core.config.protocols import ConfigProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.filesystem.descriptor_io import open_descriptor
from core.filesystem.text_read import read_text_if_exists
from core.logging.protocols import LoggerProtocol

__all__ = (
    "STARTUP_BEEP_CONFIG_KEY",
    "emit_startup_beep_if_enabled",
    "startup_beep_platform",
)

if TYPE_CHECKING:
    type StartupBeepPlatform = Literal["linux", "windows"]

STARTUP_BEEP_CONFIG_KEY = "SYSTEM.RUNTIME.STARTUP_BEEP"
_LINUX_KDMKTONE_IOCTL = 0x4B30
_LINUX_INPUT_CLASS_PATH = "/sys/class/input"
_LINUX_SND_TONE_BIT = 0b100
_PC_SPEAKER_CLOCK_TICK_RATE = 1_193_180
_STARTUP_BEEP_FREQUENCY_HZ = 1200
_STARTUP_BEEP_DURATION_MS = 90
_STARTUP_BEEP_GAP_MS = 150
_STARTUP_BEEP_COUNT = 2
_LINUX_TONE_INTERVAL_MS = _STARTUP_BEEP_DURATION_MS + _STARTUP_BEEP_GAP_MS
_WINDOWS_STARTUP_BEEP_VOLUME = 0.20
_WINDOWS_CHIME_SAMPLE_RATE_HZ = 22_050
_WINDOWS_CHIME_FADE_MS = 5
_PCM16_MAX_AMPLITUDE = 32_767
_OPERATION_APPLICATION_STARTUP_BEEP = "application_startup.beep"
_LINUX_TONE_ACCESS_DENIED_ERRNOS: frozenset[int] = frozenset({errno.EACCES, errno.EPERM})
_LINUX_TONE_TERMINAL_UNAVAILABLE_ERRNOS: frozenset[int] = frozenset(
    {
        errno.EIO,
        errno.ENODEV,
        errno.ENXIO,
        errno.ENOTTY,
        errno.ENOENT,
    }
)
_LINUX_SPEAKER_ABSENT_MESSAGE = (
    "Startup beep skipped; no PC speaker tone device (pcspkr driver) is present."
)
_LINUX_TONE_ACCESS_DENIED_MESSAGE = (
    "Startup beep skipped; the PC speaker tone requires root or CAP_SYS_TTY_CONFIG. "
    "Disable SYSTEM.RUNTIME.STARTUP_BEEP to silence this warning."
)
_LINUX_TONE_TERMINAL_UNAVAILABLE_MESSAGE = (
    "Startup beep skipped; no virtual terminal (/dev/tty0) accepts the PC speaker tone. "
    "Disable SYSTEM.RUNTIME.STARTUP_BEEP to silence this warning."
)
_WINDOWS_PLAYBACK_FAILED_MESSAGE = (
    "Startup beep skipped; Windows could not play the tone on the default audio device."
)
_STARTUP_BEEP_FAILED_MESSAGE = "Startup beep could not be emitted."

if sys.platform.startswith("linux"):
    import fcntl

    def _linux_ioctl(fd: int, request: int, arg: int) -> int:
        return fcntl.ioctl(fd, request, arg)

else:

    def _linux_ioctl(fd: int, request: int, arg: int) -> int:
        _ = fd, request, arg
        raise StateError("Linux console tone ioctl is unavailable on this platform.")


if sys.platform == "win32":
    import winsound

    def _windows_play_wav(wav_bytes: bytes) -> None:
        winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_NODEFAULT)

else:

    def _windows_play_wav(wav_bytes: bytes) -> None:
        _ = wav_bytes
        raise StateError("Windows sound playback is unavailable on this platform.")


def startup_beep_platform() -> StartupBeepPlatform | None:
    system_name = platform.system()
    if system_name == "Linux":
        return "linux"
    if system_name == "Windows":
        return "windows"
    return None


def _linux_snd_capabilities_support_tone(capabilities_text: str) -> bool:
    words = capabilities_text.split()
    if not words:
        return False
    try:
        capability_mask = int(words[-1], 16)
    except ValueError:
        return False
    return bool(capability_mask & _LINUX_SND_TONE_BIT)


def _linux_tone_speaker_present(input_class_path: str = _LINUX_INPUT_CLASS_PATH) -> bool:
    try:
        entries = sorted(os.listdir(input_class_path))
    except OSError:
        return False
    for entry in entries:
        if not entry.startswith("input"):
            continue
        capabilities_text = read_text_if_exists(
            os.path.join(input_class_path, entry, "capabilities", "snd")
        )
        if capabilities_text is not None and _linux_snd_capabilities_support_tone(
            capabilities_text
        ):
            return True
    return False


def _linux_tone_terminal_path() -> str:
    return os.path.join(os.sep, "dev", "tty0")


def _linux_kdmktone_argument() -> int:
    frequency_divisor = _PC_SPEAKER_CLOCK_TICK_RATE // _STARTUP_BEEP_FREQUENCY_HZ
    return frequency_divisor | (_STARTUP_BEEP_DURATION_MS << 16)


def _emit_linux_terminal_tone() -> None:
    file_descriptor = open_descriptor(_linux_tone_terminal_path(), os.O_WRONLY | os.O_NOCTTY)
    try:
        _linux_ioctl(file_descriptor, _LINUX_KDMKTONE_IOCTL, _linux_kdmktone_argument())
    finally:
        os.close(file_descriptor)


def _chime_tone_envelope(sample_index: int, sample_count: int, fade_sample_count: int) -> float:
    edge_distance = min(sample_index, sample_count - 1 - sample_index)
    if edge_distance >= fade_sample_count:
        return 1.0
    return 0.5 * (1.0 - math.cos(math.pi * edge_distance / fade_sample_count))


def _build_startup_chime_wav() -> bytes:
    sample_rate = _WINDOWS_CHIME_SAMPLE_RATE_HZ
    tone_sample_count = sample_rate * _STARTUP_BEEP_DURATION_MS // 1000
    gap_sample_count = sample_rate * _STARTUP_BEEP_GAP_MS // 1000
    fade_sample_count = sample_rate * _WINDOWS_CHIME_FADE_MS // 1000
    peak_amplitude = _WINDOWS_STARTUP_BEEP_VOLUME * _PCM16_MAX_AMPLITUDE
    angular_step = 2.0 * math.pi * _STARTUP_BEEP_FREQUENCY_HZ / sample_rate
    tone = array(
        "h",
        (
            round(
                peak_amplitude
                * _chime_tone_envelope(sample_index, tone_sample_count, fade_sample_count)
                * math.sin(angular_step * sample_index)
            )
            for sample_index in range(tone_sample_count)
        ),
    )
    samples = array("h")
    for beep_index in range(_STARTUP_BEEP_COUNT):
        if beep_index > 0:
            samples.extend([0] * gap_sample_count)
        samples.extend(tone)
    if sys.byteorder == "big":
        samples.byteswap()
    buffer = io.BytesIO()
    with wave.Wave_write(buffer) as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(samples.tobytes())
    return buffer.getvalue()


def _emit_windows_speaker_chime() -> None:
    _windows_play_wav(_build_startup_chime_wav())


async def _emit_linux_startup_beep(
    logger: LoggerProtocol,
    *,
    speaker_probe: Callable[[], bool],
    tone_emitter: Callable[[], None],
    sleep_func: Callable[[float], Awaitable[None]],
) -> None:
    if not await asyncio.to_thread(speaker_probe):
        logger.debug(_LINUX_SPEAKER_ABSENT_MESSAGE)
        return
    try:
        for beep_index in range(_STARTUP_BEEP_COUNT):
            if beep_index > 0:
                await sleep_func(float(_LINUX_TONE_INTERVAL_MS) / 1000.0)
            await asyncio.to_thread(tone_emitter)
    except (OSError, StateError, ValueError) as exception:
        handled_message: str | None = None
        if isinstance(exception, OSError):
            if exception.errno in _LINUX_TONE_ACCESS_DENIED_ERRNOS:
                handled_message = _LINUX_TONE_ACCESS_DENIED_MESSAGE
            elif exception.errno in _LINUX_TONE_TERMINAL_UNAVAILABLE_ERRNOS:
                handled_message = _LINUX_TONE_TERMINAL_UNAVAILABLE_MESSAGE
        if handled_message is not None:
            log_handled_exception(
                logger,
                exception,
                message=handled_message,
                operation=_OPERATION_APPLICATION_STARTUP_BEEP,
                level="warning",
            )
            return
        log_exception(
            logger,
            exception,
            message=_STARTUP_BEEP_FAILED_MESSAGE,
            operation=_OPERATION_APPLICATION_STARTUP_BEEP,
            level="warning",
        )


async def _emit_windows_startup_beep(
    logger: LoggerProtocol,
    *,
    chime_emitter: Callable[[], None],
) -> None:
    try:
        await asyncio.to_thread(chime_emitter)
    except RuntimeError as exception:
        log_handled_exception(
            logger,
            exception,
            message=_WINDOWS_PLAYBACK_FAILED_MESSAGE,
            operation=_OPERATION_APPLICATION_STARTUP_BEEP,
            level="info",
        )
    except (OSError, StateError, ValueError) as exception:
        log_exception(
            logger,
            exception,
            message=_STARTUP_BEEP_FAILED_MESSAGE,
            operation=_OPERATION_APPLICATION_STARTUP_BEEP,
            level="warning",
        )


async def emit_startup_beep_if_enabled(
    config: ConfigProtocol,
    logger: LoggerProtocol,
    *,
    platform_func: Callable[[], StartupBeepPlatform | None] = startup_beep_platform,
    linux_speaker_probe: Callable[[], bool] = _linux_tone_speaker_present,
    linux_tone_emitter: Callable[[], None] = _emit_linux_terminal_tone,
    windows_chime_emitter: Callable[[], None] = _emit_windows_speaker_chime,
    sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    if not config.get_bool(STARTUP_BEEP_CONFIG_KEY):
        return
    host_platform = platform_func()
    if host_platform == "linux":
        await _emit_linux_startup_beep(
            logger,
            speaker_probe=linux_speaker_probe,
            tone_emitter=linux_tone_emitter,
            sleep_func=sleep_func,
        )
    elif host_platform == "windows":
        await _emit_windows_startup_beep(logger, chime_emitter=windows_chime_emitter)

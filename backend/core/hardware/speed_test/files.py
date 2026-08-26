"""SoAI - Disk speed test file access (platform-specific) [backend/core/hardware/speed_test/files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from types import TracebackType
from typing import TYPE_CHECKING, Literal

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ProcessError, StateError, ValidationError
from core.files.windows_handle_operations import close_windows_handle
from core.logging.trace import get_logger
from core.platform.os import is_windows
from core.system.windows_ctypes import last_windows_error, load_kernel32

if TYPE_CHECKING:
    type SpeedTestFileImpl = _WindowsUnbufferedFile | _PosixSpeedTestFile

__all__ = ("open_for_speed_test",)

LOGGER_NAME = "SoAI.core.hardware.files"
OPERATION_HARDWARE_SPEED_TEST_FILES_INIT_CLOSE_FD = "hardware.speed_test.files.init.close_fd"
OPERATION_HARDWARE_SPEED_TEST_FILES_INIT_CLOSE_FILE = "hardware.speed_test.files.init.close_file"


_WINDOWS_GENERIC_READ = 0x80000000
_WINDOWS_OPEN_EXISTING = 3
_WINDOWS_FILE_FLAG_NO_BUFFERING = 0x20000000
_WINDOWS_FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
_WINDOWS_INVALID_HANDLE_VALUE = -1
_WINDOWS_ERROR_HANDLE_EOF = 38
_WINDOWS_UNBUFFERED_ALIGNMENT_BYTES = 4096


def _require_posix_fadvise() -> None:
    try:
        if not callable(os.posix_fadvise) or not isinstance(os.POSIX_FADV_DONTNEED, int):
            raise StateError("Disk speed test requires POSIX fadvise support.")
    except AttributeError as exception:
        if not is_windows():
            raise StateError("Disk speed test requires POSIX fadvise support.") from exception


def _drop_file_cache(file_descriptor: int) -> None:
    _require_posix_fadvise()
    os.posix_fadvise(file_descriptor, 0, 0, os.POSIX_FADV_DONTNEED)


class _WindowsUnbufferedFile:
    handle: int
    buffer_size: int
    closed: bool
    kernel32: ctypes.CDLL

    def __init__(self, handle: int, buffer_size: int, kernel32: ctypes.CDLL) -> None:
        self.handle = int(handle)
        self.buffer_size = int(buffer_size)
        self.kernel32 = kernel32
        self.closed = False
        if not is_windows():
            raise StateError("_WindowsUnbufferedFile initialized on non-Windows platform")

    def read(self, size: int) -> bytes:
        if self.closed:
            raise ValidationError("I/O operation on closed file")
        if not is_windows():
            raise StateError("_WindowsUnbufferedFile used on non-Windows platform")
        if size < 0:
            raise ValidationError("Read size must be non-negative.")
        if size == 0:
            return b""
        buffer, aligned_address, aligned_size = _allocate_aligned_windows_buffer(size)
        bytes_read = wintypes.DWORD(0)
        success = self.kernel32.ReadFile(
            wintypes.HANDLE(self.handle),
            ctypes.c_void_p(aligned_address),
            aligned_size,
            ctypes.byref(bytes_read),
            None,
        )
        if not success:
            error_code = last_windows_error()
            if error_code == _WINDOWS_ERROR_HANDLE_EOF:
                return b""
            raise ProcessError("ReadFile failed.", details={"error_code": error_code})
        if bytes_read.value == 0:
            return b""
        _ = buffer
        return ctypes.string_at(aligned_address, min(size, bytes_read.value))

    def close(self) -> None:
        if not self.closed:
            if not is_windows():
                raise StateError("_WindowsUnbufferedFile closed on non-Windows platform")
            close_windows_handle(self.handle)
            self.closed = True

    def __enter__(self) -> _WindowsUnbufferedFile:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        _ = exc_type, traceback
        try:
            self.close()
        except OSError as close_exception:
            if exc_value is None:
                raise
            exc_value.add_note(f"Failed to close Windows speed test handle: {close_exception}")
        return False


def _allocate_aligned_windows_buffer(
    size: int,
) -> tuple[ctypes.Array[ctypes.c_char], int, int]:
    aligned_size = (
        (size + _WINDOWS_UNBUFFERED_ALIGNMENT_BYTES - 1)
        // _WINDOWS_UNBUFFERED_ALIGNMENT_BYTES
        * _WINDOWS_UNBUFFERED_ALIGNMENT_BYTES
    )
    buffer = ctypes.create_string_buffer(
        aligned_size + _WINDOWS_UNBUFFERED_ALIGNMENT_BYTES - 1,
    )
    buffer_address = ctypes.addressof(buffer)
    aligned_address = (
        (buffer_address + _WINDOWS_UNBUFFERED_ALIGNMENT_BYTES - 1)
        // _WINDOWS_UNBUFFERED_ALIGNMENT_BYTES
        * _WINDOWS_UNBUFFERED_ALIGNMENT_BYTES
    )
    return buffer, aligned_address, aligned_size


def _open_windows_unbuffered(file_path: str, buffer_size: int) -> _WindowsUnbufferedFile:
    if not is_windows():
        raise StateError("_open_windows_unbuffered called on non-Windows platform")
    kernel32 = load_kernel32()
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    handle = kernel32.CreateFileW(
        file_path,
        _WINDOWS_GENERIC_READ,
        0,
        None,
        _WINDOWS_OPEN_EXISTING,
        _WINDOWS_FILE_FLAG_NO_BUFFERING | _WINDOWS_FILE_FLAG_SEQUENTIAL_SCAN,
        None,
    )
    if handle == wintypes.HANDLE(_WINDOWS_INVALID_HANDLE_VALUE).value:
        error_code = last_windows_error()
        raise ProcessError("CreateFileW failed.", details={"error_code": error_code})
    return _WindowsUnbufferedFile(handle, buffer_size, kernel32)


class _PosixSpeedTestFile:

    def __init__(self, path: str) -> None:
        logger = get_logger(LOGGER_NAME)
        opened_file_descriptor = os.open(path, os.O_RDONLY)
        file_obj = None
        try:
            file_obj = os.fdopen(opened_file_descriptor, "rb", buffering=0)
            self.file = file_obj
            self.file_descriptor = self.file.fileno()
            _drop_file_cache(self.file_descriptor)
        except (OSError, ValueError, StateError):
            if file_obj is None:
                try:
                    os.close(opened_file_descriptor)
                except OSError as close_err:
                    log_handled_exception(
                        logger,
                        close_err,
                        message="Failed to close opened file descriptor after speed test initialization failure (non-critical).",
                        operation=OPERATION_HARDWARE_SPEED_TEST_FILES_INIT_CLOSE_FD,
                        level="debug",
                    )
            else:
                try:
                    file_obj.close()
                except OSError as close_err:
                    log_handled_exception(
                        logger,
                        close_err,
                        message="Failed to close file after speed test initialization failure (non-critical).",
                        operation=OPERATION_HARDWARE_SPEED_TEST_FILES_INIT_CLOSE_FILE,
                        level="debug",
                    )
            raise

    def read(self, size: int) -> bytes:
        if self.file.closed:
            raise ValidationError("I/O operation on closed file")
        if size < 0:
            raise ValidationError("Read size must be non-negative.")
        if size == 0:
            return b""
        return self.file.read(size)

    def close(self) -> None:
        try:
            _drop_file_cache(self.file_descriptor)
        finally:
            self.file.close()

    def __enter__(self) -> _PosixSpeedTestFile:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        self.close()
        return False


def open_for_speed_test(file_path: str, block_bytes: int) -> SpeedTestFileImpl:
    if is_windows():
        return _open_windows_unbuffered(file_path, block_bytes)
    return _PosixSpeedTestFile(file_path)

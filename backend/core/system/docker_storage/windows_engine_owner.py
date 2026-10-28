"""SoAI - Windows Docker engine pipe server owner resolution [backend/core/system/docker_storage/windows_engine_owner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import NoReturn

from core.system.docker_storage.location import (
    DOCKER_STORAGE_ACCESS_DENIED,
    DOCKER_STORAGE_CHANGED,
    DOCKER_STORAGE_UNAVAILABLE,
    reject_docker_storage,
)
from core.system.windows_ctypes import last_windows_error, load_kernel32, load_windows_library

__all__ = (
    "WindowsEngineOwner",
    "resolve_windows_engine_owner",
)

_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_ERROR_FILE_NOT_FOUND = 2
_ERROR_ACCESS_DENIED = 5
_ERROR_PIPE_BUSY = 231
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_TOKEN_QUERY = 0x0008
_TOKEN_USER_CLASS = 1
_PIPE_WAIT_MILLISECONDS = 2000
_IMAGE_PATH_CHARACTERS = 32768


class _SidAndAttributes(ctypes.Structure):
    _fields_ = (("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD))


class _TokenUser(ctypes.Structure):
    _fields_ = (("User", _SidAndAttributes),)


@dataclass(frozen=True, slots=True)
class WindowsEngineOwner:
    process_id: int
    user_sid: str
    image_path: str


def resolve_windows_engine_owner(pipe_path: str) -> WindowsEngineOwner:
    kernel32 = load_kernel32()
    advapi32 = load_windows_library("advapi32", use_last_error=True)
    _declare_signatures(kernel32, advapi32)
    connected_at = wintypes.FILETIME()
    kernel32.GetSystemTimeAsFileTime(ctypes.byref(connected_at))
    pipe = _open_pipe(kernel32, pipe_path)
    try:
        process_id = wintypes.ULONG()
        if not kernel32.GetNamedPipeServerProcessId(pipe, ctypes.byref(process_id)):
            _reject_last_error("engine_pipe_server_unresolved")
        process = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value)
        if not process:
            _reject_last_error("engine_process_unavailable")
        try:
            _require_process_predates(kernel32, process, connected_at)
            return WindowsEngineOwner(
                process_id=int(process_id.value),
                user_sid=_process_user_sid(advapi32, kernel32, process),
                image_path=_process_image_path(kernel32, process),
            )
        finally:
            kernel32.CloseHandle(process)
    finally:
        kernel32.CloseHandle(pipe)


def _open_pipe(kernel32: ctypes.CDLL, pipe_path: str) -> int:
    for attempt in range(2):
        pipe = kernel32.CreateFileW(
            pipe_path, _GENERIC_READ | _GENERIC_WRITE, 0, None, _OPEN_EXISTING, 0, None
        )
        if pipe is not None and pipe != wintypes.HANDLE(-1).value:
            return int(pipe)
        error = last_windows_error()
        if error != _ERROR_PIPE_BUSY or attempt:
            _reject_windows_error(error, "engine_pipe_unavailable")
        kernel32.WaitNamedPipeW(pipe_path, _PIPE_WAIT_MILLISECONDS)
    _reject_windows_error(_ERROR_PIPE_BUSY, "engine_pipe_unavailable")


def _require_process_predates(
    kernel32: ctypes.CDLL, process: int, connected_at: wintypes.FILETIME
) -> None:
    created = wintypes.FILETIME()
    unused = (wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME())
    if not kernel32.GetProcessTimes(
        process, ctypes.byref(created), *(ctypes.byref(value) for value in unused)
    ):
        _reject_last_error("engine_process_times_unavailable")
    if _filetime_value(created) > _filetime_value(connected_at):
        reject_docker_storage(DOCKER_STORAGE_CHANGED, "engine_process_replaced")


def _process_user_sid(advapi32: ctypes.CDLL, kernel32: ctypes.CDLL, process: int) -> str:
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, _TOKEN_QUERY, ctypes.byref(token)):
        _reject_last_error("engine_token_unavailable")
    try:
        required = wintypes.DWORD()
        advapi32.GetTokenInformation(token, _TOKEN_USER_CLASS, None, 0, ctypes.byref(required))
        buffer = ctypes.create_string_buffer(max(int(required.value), ctypes.sizeof(_TokenUser)))
        if not advapi32.GetTokenInformation(
            token, _TOKEN_USER_CLASS, buffer, len(buffer), ctypes.byref(required)
        ):
            _reject_last_error("engine_token_user_unavailable")
        string_sid = ctypes.c_void_p()
        if (
            not advapi32.ConvertSidToStringSidW(
                _TokenUser.from_buffer(buffer).User.Sid, ctypes.byref(string_sid)
            )
            or string_sid.value is None
        ):
            _reject_last_error("engine_token_user_unavailable")
        try:
            return ctypes.wstring_at(string_sid.value)
        finally:
            kernel32.LocalFree(string_sid)
    finally:
        kernel32.CloseHandle(token)


def _process_image_path(kernel32: ctypes.CDLL, process: int) -> str:
    buffer = ctypes.create_unicode_buffer(_IMAGE_PATH_CHARACTERS)
    length = wintypes.DWORD(len(buffer))
    if not kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(length)):
        _reject_last_error("engine_image_unavailable")
    return buffer.value


def _filetime_value(value: wintypes.FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _reject_last_error(reason: str) -> NoReturn:
    _reject_windows_error(last_windows_error(), reason)


def _reject_windows_error(error: int, reason: str) -> NoReturn:
    if error == _ERROR_ACCESS_DENIED:
        reject_docker_storage(DOCKER_STORAGE_ACCESS_DENIED, reason)
    if error == _ERROR_FILE_NOT_FOUND:
        reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "engine_pipe_missing")
    reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, reason)


def _declare_signatures(kernel32: ctypes.CDLL, advapi32: ctypes.CDLL) -> None:
    handle_pointer = ctypes.POINTER(wintypes.HANDLE)
    filetime_pointer = ctypes.POINTER(wintypes.FILETIME)
    kernel32.GetSystemTimeAsFileTime.argtypes = (filetime_pointer,)
    kernel32.GetSystemTimeAsFileTime.restype = None
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.WaitNamedPipeW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
    kernel32.WaitNamedPipeW.restype = wintypes.BOOL
    kernel32.GetNamedPipeServerProcessId.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.ULONG),
    )
    kernel32.GetNamedPipeServerProcessId.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, *(filetime_pointer,) * 4)
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel32.LocalFree.restype = ctypes.c_void_p
    advapi32.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, handle_pointer)
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

"""SoAI - Native Windows registry and file access for Docker Desktop storage mapping [backend/core/system/docker_storage/windows_desktop_host.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import NoReturn

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import read_regular_file_no_symlink
from core.system.docker_storage.location import (
    DOCKER_STORAGE_ACCESS_DENIED,
    DOCKER_STORAGE_UNAVAILABLE,
    DOCKER_STORAGE_UNMAPPED,
    observe_host_path,
    reject_docker_storage,
)
from core.system.docker_storage.windows_desktop_storage import WindowsDesktopStorageHost
from core.system.docker_storage.windows_engine_owner import resolve_windows_engine_owner
from core.system.windows_ctypes import load_kernel32, load_windows_library

__all__ = ("build_windows_desktop_storage_host",)

_MAX_SETTINGS_BYTES = 1024 * 1024
_MAX_REGISTRY_VALUE_BYTES = 64 * 1024
_MAX_EXPANDED_CHARACTERS = 32768
_REGISTRY_KEY_NAME_CHARACTERS = 256
_PREDEFINED_KEYS = (("HKLM", 0x80000002), ("HKU", 0x80000003))
_KEY_READ_WOW64_64KEY = 0x20119
_REG_SZ = 1
_REG_EXPAND_SZ = 2
_ERROR_SUCCESS = 0
_ERROR_FILE_NOT_FOUND = 2
_ERROR_ACCESS_DENIED = 5
_ERROR_MORE_DATA = 234
_ERROR_NO_MORE_ITEMS = 259


def build_windows_desktop_storage_host() -> WindowsDesktopStorageHost:
    advapi32 = load_windows_library("advapi32")
    kernel32 = load_kernel32()
    _declare_signatures(advapi32, kernel32)
    return WindowsDesktopStorageHost(
        resolve_engine_owner=resolve_windows_engine_owner,
        read_registry_text=lambda hive, key, name: _read_registry_text(advapi32, hive, key, name),
        list_registry_subkeys=lambda hive, key: _list_registry_subkeys(advapi32, hive, key),
        expand_system_text=lambda value: _expand_system_text(kernel32, value),
        observe_path=observe_host_path,
        read_settings=_read_settings,
    )


def _read_registry_text(advapi32: ctypes.CDLL, hive: str, key: str, value_name: str) -> str | None:
    handle = _open_registry_key(advapi32, hive, key)
    if handle is None:
        return None
    try:
        value_type = wintypes.DWORD()
        size = wintypes.DWORD(0)
        status = advapi32.RegQueryValueExW(
            handle, value_name, None, ctypes.byref(value_type), None, ctypes.byref(size)
        )
        while status in (_ERROR_SUCCESS, _ERROR_MORE_DATA):
            if value_type.value not in (_REG_SZ, _REG_EXPAND_SZ):
                reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "registry_value_malformed")
            if size.value > _MAX_REGISTRY_VALUE_BYTES:
                reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "registry_value_malformed")
            buffer = ctypes.create_string_buffer(size.value + 2)
            size = wintypes.DWORD(len(buffer))
            status = advapi32.RegQueryValueExW(
                handle, value_name, None, ctypes.byref(value_type), buffer, ctypes.byref(size)
            )
            if status == _ERROR_SUCCESS:
                text = buffer.raw[: size.value - size.value % 2].decode("utf-16-le")
                return text.split("\0", 1)[0]
        if status == _ERROR_FILE_NOT_FOUND:
            return None
        _reject_registry_status(status)
    finally:
        advapi32.RegCloseKey(handle)


def _list_registry_subkeys(advapi32: ctypes.CDLL, hive: str, key: str) -> tuple[str, ...]:
    handle = _open_registry_key(advapi32, hive, key)
    if handle is None:
        return ()
    try:
        names: list[str] = []
        while True:
            name = ctypes.create_unicode_buffer(_REGISTRY_KEY_NAME_CHARACTERS)
            length = wintypes.DWORD(len(name))
            status = advapi32.RegEnumKeyExW(
                handle, len(names), name, ctypes.byref(length), None, None, None, None
            )
            if status == _ERROR_NO_MORE_ITEMS:
                return tuple(names)
            if status != _ERROR_SUCCESS:
                _reject_registry_status(status)
            names.append(name.value)
    finally:
        advapi32.RegCloseKey(handle)


def _open_registry_key(advapi32: ctypes.CDLL, hive: str, key: str) -> wintypes.HKEY | None:
    root = next((value for name, value in _PREDEFINED_KEYS if name == hive), None)
    if root is None:
        raise ValidationError("Registry hive is not supported for Docker storage mapping.")
    handle = wintypes.HKEY()
    status = advapi32.RegOpenKeyExW(
        wintypes.HKEY(root - (1 << 32)), key, 0, _KEY_READ_WOW64_64KEY, ctypes.byref(handle)
    )
    if status == _ERROR_FILE_NOT_FOUND:
        return None
    if status != _ERROR_SUCCESS:
        _reject_registry_status(status)
    return handle


def _reject_registry_status(status: int) -> NoReturn:
    if status == _ERROR_ACCESS_DENIED:
        reject_docker_storage(DOCKER_STORAGE_ACCESS_DENIED, "registry_access_denied")
    reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "registry_query_failed")


def _expand_system_text(kernel32: ctypes.CDLL, value: str) -> str:
    buffer = ctypes.create_unicode_buffer(_MAX_EXPANDED_CHARACTERS)
    length = kernel32.ExpandEnvironmentStringsW(value, buffer, len(buffer))
    if length == 0:
        reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "environment_expansion_failed")
    if length > len(buffer):
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "environment_expansion_too_long")
    return buffer.value


def _read_settings(path: str) -> bytes:
    try:
        contents = read_regular_file_no_symlink(path, max_bytes=_MAX_SETTINGS_BYTES)
    except ValidationError as exception:
        if isinstance(exception.__cause__, PermissionError):
            reject_docker_storage(DOCKER_STORAGE_ACCESS_DENIED, "settings_access_denied")
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "settings_unreadable")
    except OSError:
        reject_docker_storage(DOCKER_STORAGE_UNAVAILABLE, "settings_unreadable")
    if len(contents) > _MAX_SETTINGS_BYTES:
        reject_docker_storage(DOCKER_STORAGE_UNMAPPED, "settings_too_large")
    return contents


def _declare_signatures(advapi32: ctypes.CDLL, kernel32: ctypes.CDLL) -> None:
    dword_pointer = ctypes.POINTER(wintypes.DWORD)
    advapi32.RegOpenKeyExW.argtypes = (
        wintypes.HKEY,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HKEY),
    )
    advapi32.RegOpenKeyExW.restype = wintypes.LONG
    advapi32.RegQueryValueExW.argtypes = (
        wintypes.HKEY,
        wintypes.LPCWSTR,
        dword_pointer,
        dword_pointer,
        ctypes.c_void_p,
        dword_pointer,
    )
    advapi32.RegQueryValueExW.restype = wintypes.LONG
    advapi32.RegEnumKeyExW.argtypes = (
        wintypes.HKEY,
        wintypes.DWORD,
        wintypes.LPWSTR,
        dword_pointer,
        dword_pointer,
        wintypes.LPWSTR,
        dword_pointer,
        ctypes.c_void_p,
    )
    advapi32.RegEnumKeyExW.restype = wintypes.LONG
    advapi32.RegCloseKey.argtypes = (wintypes.HKEY,)
    advapi32.RegCloseKey.restype = wintypes.LONG
    kernel32.ExpandEnvironmentStringsW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    )
    kernel32.ExpandEnvironmentStringsW.restype = wintypes.DWORD

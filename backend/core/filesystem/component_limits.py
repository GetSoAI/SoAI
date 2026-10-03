"""SoAI - Destination filesystem component budgets [backend/core/filesystem/component_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.path_coercion import normalize_filesystem_path
from core.system.windows_ctypes import last_windows_error, load_kernel32

__all__ = ("filesystem_component_limit", "filesystem_component_size")


def filesystem_component_limit(directory: str) -> int:
    existing = os.path.abspath(directory or os.curdir)
    while not os.path.exists(normalize_filesystem_path(existing)):
        parent = os.path.dirname(existing)
        if parent == existing:
            raise ValidationError("Destination filesystem cannot be resolved.")
        existing = parent
    if os.name != "nt":
        limit = os.pathconf(existing, "PC_NAME_MAX")
    else:
        kernel = load_kernel32()
        volume_path = ctypes.create_unicode_buffer(32768)
        get_volume_path = kernel.GetVolumePathNameW
        get_volume_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        get_volume_path.restype = wintypes.BOOL
        if not get_volume_path(normalize_filesystem_path(existing), volume_path, len(volume_path)):
            raise StateError(
                "Cannot resolve destination volume.",
                details={"windows_error": last_windows_error()},
            )
        maximum_component = wintypes.DWORD()
        get_volume_information = kernel.GetVolumeInformationW
        get_volume_information.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        get_volume_information.restype = wintypes.BOOL
        if not get_volume_information(
            volume_path.value, None, 0, None, ctypes.byref(maximum_component), None, None, 0
        ):
            raise StateError(
                "Cannot read destination volume limits.",
                details={"windows_error": last_windows_error()},
            )
        limit = maximum_component.value
    if limit <= 0:
        raise ValidationError("Destination filesystem has no finite component budget.")
    return min(255, limit)


def filesystem_component_size(name: str) -> int:
    if os.name == "nt":
        return len(name.encode("utf-16-le", "surrogatepass")) // 2
    return len(os.fsencode(name))

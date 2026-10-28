"""SoAI - Windows network and unmapped drive path detection [backend/core/filesystem/windows_remote_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ntpath
from ctypes import wintypes

from core.platform.os import is_windows
from core.system.windows_ctypes import load_kernel32

__all__ = ("is_windows_remote_or_unmapped_path",)

_DRIVE_NO_ROOT_DIR = 1
_DRIVE_REMOTE = 4
_EXTENDED_PREFIX = "\\\\?\\"
_EXTENDED_UNC_PREFIX = "\\\\?\\UNC\\"
_DEVICE_PREFIX = "\\\\.\\"


def is_windows_remote_or_unmapped_path(path: str) -> bool:
    if not is_windows() or not path.strip():
        return False
    candidate = path.strip()
    if candidate.upper().startswith(_EXTENDED_UNC_PREFIX):
        return True
    if candidate.startswith(_DEVICE_PREFIX):
        return False
    if candidate.startswith(_EXTENDED_PREFIX):
        candidate = candidate[len(_EXTENDED_PREFIX) :]
    elif candidate.startswith(("\\\\", "//")):
        return True
    drive, _ = ntpath.splitdrive(candidate)
    if len(drive) != 2 or drive[1] != ":":
        return False
    get_drive_type = load_kernel32().GetDriveTypeW
    get_drive_type.argtypes = [wintypes.LPCWSTR]
    get_drive_type.restype = wintypes.UINT
    return get_drive_type(f"{drive}\\") in (_DRIVE_NO_ROOT_DIR, _DRIVE_REMOTE)
